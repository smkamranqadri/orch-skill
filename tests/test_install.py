import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "herdr-calls.jsonl"
        self.plugin_root = self.root / "herdr-installed" / "orch"
        self.plugin_root.mkdir(parents=True)
        shutil.copy2(ROOT / "plugin/herdr-plugin.toml", self.plugin_root / "herdr-plugin.toml")
        shutil.copy2(ROOT / "plugin/orch", self.plugin_root / "orch")
        self.plugin_root.joinpath("orch").chmod(0o755)
        fake_herdr = self.bin / "herdr"
        shutil.copy2(ROOT / "tests/fixtures/herdr/bin/herdr", fake_herdr)
        fake_herdr.chmod(0o755)
        self.env = os.environ.copy() | {
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "ORCH_TEST_CALLS": str(self.calls),
            "ORCH_TEST_PLUGIN_ROOT": str(self.plugin_root),
            "ORCH_TEST_LINKED_FILE": str(self.root / "linked-plugin"),
        }
        self.env.pop("HERDR_ENV", None)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_fake_git(self):
        fake = self.bin / "git"
        fake.write_text('''#!/usr/bin/env python3
import os, shutil, sys
args = sys.argv[1:]
if args[:1] != ["clone"]:
    raise SystemExit("unexpected fake git command")
if os.environ.get("ORCH_TEST_GIT_FAIL") == "1":
    raise SystemExit("simulated clone failure")
source = os.environ["ORCH_TEST_SOURCE"]
dest = args[-1]
def ignore(path, names):
    return {name for name in names if name in {".git", "archive", "__pycache__"}}
shutil.copytree(source, dest, ignore=ignore)
''')
        fake.chmod(0o755)

    def run_bootstrap(self, *args, env=None, success=True):
        result = subprocess.run(
            [str(ROOT / "bootstrap.sh"), *args],
            cwd=ROOT,
            env=env or self.env,
            text=True,
            capture_output=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def run_helper(self, *args, env=None, success=True):
        result = subprocess.run(
            [str(ROOT / "scripts/install-skill.sh"), *args],
            cwd=ROOT,
            env=env or self.env,
            text=True,
            capture_output=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def herdr_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_local_install_rerun_check_and_update(self):
        first = self.run_bootstrap("install", "--source", str(ROOT))
        self.assertIn("Installed orch skill", first.stdout)
        self.assertIn('command = "orch.board-full"', first.stdout)
        self.assertIn("default sidebar key is also prefix+b", first.stdout)
        self.assertTrue((self.home / ".agents/skills/orch/SKILL.md").is_file())
        self.assertTrue((self.home / ".claude/skills/orch/SKILL.md").is_file())
        self.assertTrue((self.home / ".claude/commands/orch/start.md").is_file())
        for name in ("start", "plan", "act", "close", "model"):
            self.assertTrue((self.home / f".codex/prompts/orch-{name}.md").is_file())
        cli = self.home / ".local/bin/orch"
        self.assertTrue(cli.is_symlink())
        self.assertEqual(cli.resolve(), (ROOT / "plugin/orch").resolve())
        self.assertIn(["plugin", "link", str(ROOT / "plugin")], self.herdr_calls())

        again = self.run_bootstrap("install", "--source", str(ROOT))
        self.assertIn("already current", again.stdout)
        checked = self.run_bootstrap("check", "--source", str(ROOT))
        self.assertIn("current", checked.stdout)
        self.assertEqual(
            json.loads((self.home / ".agents/skills/orch/.orch-install.json").read_text()),
            {"managed_by": "orch-bootstrap", "source": str(ROOT)},
        )

        installed_skill = self.home / ".agents/skills/orch/SKILL.md"
        installed_skill.write_text(installed_skill.read_text() + "\nlocal drift\n")
        update = self.run_bootstrap("update", "--source", str(ROOT))
        self.assertIn("Backed up previous orch skill", update.stdout)
        self.assertNotIn("local drift", installed_skill.read_text())
        self.assertTrue(list((self.home / ".agents").glob("orch-backup-*.tgz")))
        self.run_bootstrap("check", "--source", str(ROOT))

    def test_release_install_and_update_use_github_plugin_path(self):
        self._write_fake_git()
        env = self.env | {"ORCH_TEST_SOURCE": str(ROOT)}

        self.run_bootstrap("install", env=env)

        calls = self.herdr_calls()
        self.assertIn(["plugin", "install", "smkamranqadri/orch-skill/plugin", "--yes"], calls)
        self.assertEqual((self.home / ".local/bin/orch").resolve(), (self.plugin_root / "orch").resolve())
        self.assertTrue((self.home / ".agents/skills/orch/SKILL.md").is_file())
        self.run_bootstrap("check", env=env)

        self.run_bootstrap("update", env=env)
        self.assertIn(["plugin", "update", "orch", "--yes"], self.herdr_calls())

    def test_foreign_skill_path_is_preserved_and_refused(self):
        foreign = self.home / ".agents/skills/orch"
        foreign.mkdir(parents=True)
        sentinel = foreign / "mine.txt"
        sentinel.write_text("keep this file\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite a foreign path", result.stderr)
        self.assertEqual(sentinel.read_text(), "keep this file\n")
        self.assertFalse((foreign / ".orch-install.json").exists())

    def test_foreign_install_marker_is_not_treated_as_orch_owned(self):
        foreign = self.home / ".agents/skills/orch"
        foreign.mkdir(parents=True)
        marker = foreign / ".orch-install.json"
        marker.write_text('{"managed_by":"foreign-installer"}\n')

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite a foreign path", result.stderr)
        self.assertEqual(marker.read_text(), '{"managed_by":"foreign-installer"}\n')

    def test_foreign_path_linked_on_path_is_preserved_and_refused(self):
        cli = self.home / ".local/bin/orch"
        cli.parent.mkdir(parents=True)
        cli.write_text("foreign executable\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(cli.read_text(), "foreign executable\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_install_refuses_foreign_cli_symlink(self):
        foreign = self.root / "foreign-bin/orch"
        foreign.parent.mkdir()
        foreign.write_text("#!/bin/sh\nexit 0\n")
        foreign.chmod(0o755)
        cli = self.home / ".local/bin/orch"
        cli.parent.mkdir(parents=True)
        cli.symlink_to(foreign)

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(cli.resolve(), foreign.resolve())
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_bootstrap_and_helper_require_python_311(self):
        old_python = self.bin / "python3"
        old_python.write_text('''#!/bin/sh
case "$2" in
  *"(3, 11)"*) exit 1 ;;
  *"(3, 0)"*) exit 0 ;;
esac
exec /usr/bin/python3 "$@"
''')
        old_python.chmod(0o755)
        old_env = self.env | {"PATH": str(self.bin) + os.pathsep + "/usr/bin:/bin"}

        bootstrap = self.run_bootstrap("--help", env=old_env, success=False)
        helper = self.run_helper("--help", env=old_env, success=False)

        self.assertIn("Python 3.11 or newer is required", bootstrap.stderr)
        self.assertIn("Python 3.11 or newer is required", helper.stderr)

    def test_bootstrap_rejects_missing_home_source_and_herdr(self):
        missing_home = self.env.copy()
        missing_home.pop("HOME")
        no_home = self.run_bootstrap("install", "--source", str(ROOT), env=missing_home, success=False)
        no_source = self.run_bootstrap("install", "--source", str(self.root / "missing"), success=False)
        no_herdr = self.run_bootstrap(
            "install", "--source", str(ROOT),
            env=self.env | {"PATH": "/usr/local/bin:/usr/bin:/bin"}, success=False,
        )

        self.assertIn("HOME is unset", no_home.stderr)
        self.assertIn("source is not an orch-skill repository", no_source.stderr)
        self.assertIn("herdr is required", no_herdr.stderr)

    def test_local_check_rejects_plugin_linked_to_another_directory(self):
        self.run_bootstrap("install", "--source", str(ROOT))
        cli = self.home / ".local/bin/orch"
        cli.unlink()
        cli.symlink_to(self.plugin_root / "orch")
        Path(self.env["ORCH_TEST_LINKED_FILE"]).write_text(str(self.plugin_root))

        result = self.run_bootstrap("check", "--source", str(ROOT), success=False)

        self.assertIn("Herdr orch plugin is not linked to this source checkout", result.stderr)

    def test_helper_rejects_invalid_plugin_directory(self):
        result = self.run_helper(
            "install", "--source", str(ROOT), "--plugin-dir", str(self.root), success=False
        )

        self.assertIn("plugin-dir must contain", result.stderr)
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_helper_rejects_invalid_source(self):
        result = self.run_helper(
            "install", "--source", str(self.root / "missing"), "--plugin-dir", str(self.plugin_root),
            success=False,
        )

        self.assertIn("source must contain skills/orch", result.stderr)
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_helper_rejects_missing_home(self):
        env = self.env.copy()
        env.pop("HOME")
        result = self.run_helper(
            "install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root),
            env=env, success=False,
        )

        self.assertIn("HOME is unset", result.stderr)

    def test_check_detects_skill_drift_and_missing_host_link(self):
        self.run_bootstrap("install", "--source", str(ROOT))
        installed = self.home / ".agents/skills/orch/SKILL.md"
        installed.write_text(installed.read_text() + "\ndrift\n")

        drift = self.run_bootstrap("check", "--source", str(ROOT), success=False)
        self.assertIn("installed orch skill differs from source", drift.stderr)

        self.run_bootstrap("update", "--source", str(ROOT))
        (self.home / ".codex/prompts/orch-plan.md").unlink()
        missing = self.run_bootstrap("check", "--source", str(ROOT), success=False)
        self.assertIn("Codex prompt link is missing or differs: orch-plan", missing.stderr)

    def test_check_detects_missing_claude_and_cli_links(self):
        self.run_bootstrap("install", "--source", str(ROOT))
        claude_skill = self.home / ".claude/skills/orch"
        claude_commands = self.home / ".claude/commands/orch"
        cli = self.home / ".local/bin/orch"

        claude_skill.unlink()
        first = self.run_bootstrap("check", "--source", str(ROOT), success=False)
        self.assertIn("Claude skill link is missing or differs", first.stderr)
        self.run_bootstrap("install", "--source", str(ROOT))

        claude_commands.unlink()
        second = self.run_bootstrap("check", "--source", str(ROOT), success=False)
        self.assertIn("Claude command link is missing or differs", second.stderr)
        self.run_bootstrap("install", "--source", str(ROOT))

        cli.unlink()
        third = self.run_bootstrap("check", "--source", str(ROOT), success=False)
        self.assertIn("orch CLI link is missing or differs", third.stderr)

    def test_check_refuses_unowned_skill_directory(self):
        foreign = self.home / ".agents/skills/orch"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("foreign content\n")
        Path(self.env["ORCH_TEST_LINKED_FILE"]).write_text(str(ROOT / "plugin"))

        result = self.run_bootstrap("check", "--source", str(ROOT), success=False)

        self.assertIn("refusing to inspect an unowned skill", result.stderr)

    def test_install_refuses_foreign_codex_prompt_link(self):
        prompt = self.home / ".codex/prompts/orch-start.md"
        prompt.parent.mkdir(parents=True)
        prompt.write_text("foreign prompt\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(prompt.read_text(), "foreign prompt\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_install_refuses_foreign_claude_skill_link(self):
        link = self.home / ".claude/skills/orch"
        link.parent.mkdir(parents=True)
        link.write_text("foreign skill path\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(link.read_text(), "foreign skill path\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_release_install_refuses_unresolvable_herdr_plugin_path(self):
        self._write_fake_git()
        env = self.env | {
            "ORCH_TEST_SOURCE": str(ROOT),
            "ORCH_TEST_PLUGIN_ROOT": str(self.root / "missing-plugin"),
        }

        result = self.run_bootstrap("install", env=env, success=False)

        self.assertIn("Herdr did not report the installed orch plugin directory", result.stderr)
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_release_install_reports_source_clone_failure(self):
        self._write_fake_git()
        result = self.run_bootstrap(
            "install", env=self.env | {"ORCH_TEST_GIT_FAIL": "1"}, success=False
        )

        self.assertIn("could not fetch source repository", result.stderr)
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_plugin_path_requires_orch_identity_and_valid_entrypoints(self):
        resolver = ROOT / "scripts/plugin-path.py"
        wrong_plugin = subprocess.run(
            ["python3", str(resolver)],
            input=json.dumps([{"id": "other", "path": str(self.plugin_root)}]),
            text=True,
            capture_output=True,
        )
        invalid_dir = self.root / "empty-plugin"
        invalid_dir.mkdir()
        missing_entrypoints = subprocess.run(
            ["python3", str(resolver)],
            input=json.dumps([{"id": "orch", "path": str(invalid_dir)}]),
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(wrong_plugin.returncode, 0)
        self.assertIn("did not include an orch plugin directory", wrong_plugin.stderr)
        self.assertNotEqual(missing_entrypoints.returncode, 0)
        self.assertIn("did not include an orch plugin directory", missing_entrypoints.stderr)

        wrong_manifest = self.root / "wrong-manifest-plugin"
        wrong_manifest.mkdir()
        (wrong_manifest / "herdr-plugin.toml").write_text('id = "other"\n')
        (wrong_manifest / "orch").write_text("#!/bin/sh\n")
        wrong_manifest_result = subprocess.run(
            ["python3", str(resolver)],
            input=json.dumps([{"id": "orch", "path": str(wrong_manifest)}]),
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(wrong_manifest_result.returncode, 0)
        self.assertIn("did not include an orch plugin directory", wrong_manifest_result.stderr)

        missing_executable = self.root / "missing-executable-plugin"
        missing_executable.mkdir()
        (missing_executable / "herdr-plugin.toml").write_text('id = "orch"\n')
        missing_executable_result = subprocess.run(
            ["python3", str(resolver)],
            input=json.dumps([{"id": "orch", "path": str(missing_executable)}]),
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(missing_executable_result.returncode, 0)
        self.assertIn("did not include an orch plugin directory", missing_executable_result.stderr)

        repository_root = subprocess.run(
            ["python3", str(resolver)],
            input=json.dumps([{"id": "orch", "path": str(ROOT)}]),
            text=True,
            capture_output=True,
        )
        self.assertEqual(repository_root.returncode, 0, repository_root.stderr)
        self.assertEqual(repository_root.stdout.strip(), str(ROOT / "plugin"))

        invalid_json = subprocess.run(
            ["python3", str(resolver)], input="not-json", text=True, capture_output=True
        )
        self.assertNotEqual(invalid_json.returncode, 0)
        self.assertIn("invalid Herdr plugin list JSON", invalid_json.stderr)

    def test_release_update_installs_plugin_if_herdr_has_no_existing_one(self):
        self._write_fake_git()
        env = self.env | {
            "ORCH_TEST_SOURCE": str(ROOT),
            "ORCH_TEST_UPDATE_FAIL": "1",
        }

        self.run_bootstrap("update", env=env)

        calls = self.herdr_calls()
        self.assertIn(["plugin", "update", "orch", "--yes"], calls)
        self.assertIn(["plugin", "install", "smkamranqadri/orch-skill/plugin", "--yes"], calls)


if __name__ == "__main__":
    unittest.main()
