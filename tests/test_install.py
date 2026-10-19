import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
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
        self.mutations = self.root / "herdr-mutations.jsonl"
        self.env_calls = self.root / "herdr-env-calls.jsonl"
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
            "ORCH_TEST_MUTATIONS": str(self.mutations),
            "ORCH_TEST_ENV_CALLS": str(self.env_calls),
            "ORCH_TEST_GIT_CALLS": str(self.root / "git-calls"),
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
with open(os.environ["ORCH_TEST_GIT_CALLS"], "a", encoding="utf-8") as out:
    out.write(__import__("json").dumps(args) + "\\n")
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

    def herdr_mutations(self):
        if not self.mutations.exists():
            return []
        return [json.loads(line) for line in self.mutations.read_text().splitlines()]

    def herdr_env_calls(self):
        if not self.env_calls.exists():
            return []
        return [json.loads(line) for line in self.env_calls.read_text().splitlines()]

    def tree_snapshot(self, root):
        result = {}
        for path in sorted(root.rglob("*")):
            rel = str(path.relative_to(root))
            if path.is_symlink():
                result[rel] = ("link", os.readlink(path))
            elif path.is_dir():
                result[rel] = ("dir",)
            elif path.is_file():
                result[rel] = ("file", path.read_bytes())
        return result

    def assert_no_herdr_mutations(self):
        self.assertEqual(self.herdr_mutations(), [])

    def write_fail_once_wrapper(self, name, command, fail_at=1):
        count = self.root / f"{name}-count"
        wrapper = self.bin / name
        wrapper.write_text(f'''#!/bin/sh
count_file={str(count)!r}
count=0
if [ -f "$count_file" ]; then count=$(cat "$count_file"); fi
count=$((count + 1)); printf '%s' "$count" > "$count_file"
if [ "$count" -eq {fail_at} ]; then exit 91; fi
exec {command} "$@"
''')
        wrapper.chmod(0o755)
        return count

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
        self.assertIn(["plugin", "install", "smkamranqadri/orch-skill/plugin", "--ref", "main", "--yes"], calls)
        self.assertEqual((self.home / ".local/bin/orch").resolve(), (self.plugin_root / "orch").resolve())
        self.assertTrue((self.home / ".agents/skills/orch/SKILL.md").is_file())
        self.run_bootstrap("check", env=env)

        self.run_bootstrap("update", env=env)
        self.assertIn(["plugin", "update", "smkamranqadri/orch-skill/plugin", "--yes"], self.herdr_calls())

    def test_foreign_skill_path_is_preserved_and_refused(self):
        foreign = self.home / ".agents/skills/orch"
        foreign.mkdir(parents=True)
        sentinel = foreign / "mine.txt"
        sentinel.write_text("keep this file\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite a foreign path", result.stderr)
        self.assertEqual(sentinel.read_text(), "keep this file\n")
        self.assertFalse((foreign / ".orch-install.json").exists())
        self.assert_no_herdr_mutations()

    def test_foreign_install_marker_is_not_treated_as_orch_owned(self):
        foreign = self.home / ".agents/skills/orch"
        foreign.mkdir(parents=True)
        marker = foreign / ".orch-install.json"
        marker.write_text('{"managed_by":"foreign-installer"}\n')

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite a foreign path", result.stderr)
        self.assertEqual(marker.read_text(), '{"managed_by":"foreign-installer"}\n')
        self.assert_no_herdr_mutations()

    def test_foreign_path_linked_on_path_is_preserved_and_refused(self):
        cli = self.home / ".local/bin/orch"
        cli.parent.mkdir(parents=True)
        cli.write_text("foreign executable\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(cli.read_text(), "foreign executable\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())
        self.assert_no_herdr_mutations()

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
        self.assert_no_herdr_mutations()

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
        self.assert_no_herdr_mutations()

    def test_local_check_rejects_plugin_linked_to_another_directory(self):
        self.run_bootstrap("install", "--source", str(ROOT))
        self.mutations.write_text("")
        cli = self.home / ".local/bin/orch"
        cli.unlink()
        cli.symlink_to(self.plugin_root / "orch")
        Path(self.env["ORCH_TEST_LINKED_FILE"]).write_text(str(self.plugin_root))

        result = self.run_bootstrap("check", "--source", str(ROOT), success=False)

        self.assertIn("Herdr orch plugin is not linked to this source checkout", result.stderr)
        self.assert_no_herdr_mutations()

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
        self.assert_no_herdr_mutations()

    def test_install_refuses_foreign_codex_prompt_link(self):
        prompt = self.home / ".codex/prompts/orch-start.md"
        prompt.parent.mkdir(parents=True)
        prompt.write_text("foreign prompt\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(prompt.read_text(), "foreign prompt\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())
        self.assert_no_herdr_mutations()

    def test_install_refuses_foreign_claude_skill_link(self):
        link = self.home / ".claude/skills/orch"
        link.parent.mkdir(parents=True)
        link.write_text("foreign skill path\n")

        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)

        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assertEqual(link.read_text(), "foreign skill path\n")
        self.assertFalse((self.home / ".agents/skills/orch").exists())
        self.assert_no_herdr_mutations()

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
        self.assert_no_herdr_mutations()

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
        self.assertIn(["plugin", "update", "smkamranqadri/orch-skill/plugin", "--yes"], calls)
        self.assertIn(["plugin", "install", "smkamranqadri/orch-skill/plugin", "--ref", "main", "--yes"], calls)

    def test_preflight_rejections_leave_herdr_mutation_log_empty(self):
        foreign = self.home / ".local/bin/orch"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("foreign executable\n")
        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)
        self.assertIn("refusing to overwrite existing path", result.stderr)
        self.assert_no_herdr_mutations()

    def test_destination_ancestor_file_rejected_before_any_home_writes(self):
        (self.home / ".claude").write_text("not a directory\n")
        before = self.tree_snapshot(self.home)
        result = self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertIn("destination ancestor is not a directory", result.stderr)
        self.assertEqual(self.tree_snapshot(self.home), before)

    def test_preflight_mode_is_read_only_and_rejects_blocked_ancestor(self):
        (self.home / ".claude").write_text("not a directory\n")
        before = self.tree_snapshot(self.home)
        result = self.run_helper("preflight", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertIn("destination ancestor is not a directory", result.stderr)
        self.assertEqual(self.tree_snapshot(self.home), before)

    def test_first_install_link_failure_rolls_back_entire_home_tree(self):
        before = self.tree_snapshot(self.home)
        self.write_fail_once_wrapper("ln", "/bin/ln", fail_at=2)
        result = self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.tree_snapshot(self.home), before)

    def test_update_publish_failure_restores_previous_tree_and_bytes(self):
        self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        installed = self.home / ".agents/skills/orch/SKILL.md"
        installed.write_text("previous installed bytes\n")
        before = self.tree_snapshot(self.home)
        self.write_fail_once_wrapper("mv", "/bin/mv", fail_at=2)
        result = self.run_helper("update", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertNotEqual(result.returncode, 0)
        after = self.tree_snapshot(self.home)
        backup_keys = {key for key in after if key.startswith(".agents/orch-backup-") and key.endswith(".tgz")}
        self.assertEqual(len(backup_keys), 1)
        for key, value in before.items():
            self.assertEqual(after.get(key), value, key)
        self.assertEqual(installed.read_text(), "previous installed bytes\n")
        with tarfile.open(self.home / next(iter(backup_keys)), "r:gz") as archive:
            member = next(m for m in archive.getmembers() if m.name == "orch/SKILL.md")
            self.assertEqual(archive.extractfile(member).read(), b"previous installed bytes\n")
        self.assertFalse(any(".orch.old." in key or ".orch.new." in key for key in after))

    def test_bootstrap_herdr_failure_rolls_back_new_skill_and_plugin_registration(self):
        before = self.tree_snapshot(self.home)
        env = self.env | {"ORCH_TEST_NO_PLUGIN": "1"}
        self.write_fail_once_wrapper("ln", "/bin/ln")
        result = self.run_bootstrap("install", "--source", str(ROOT), env=env, success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.tree_snapshot(self.home), before)
        self.assertFalse(Path(self.env["ORCH_TEST_LINKED_FILE"]).exists())
        mutations = self.herdr_mutations()
        self.assertEqual([call["args"][:2] for call in mutations], [["plugin", "link"], ["plugin", "unlink"]])

    def test_later_failure_restores_previous_plugin_bytes_and_registration(self):
        previous_plugin = self.plugin_root / "orch"
        previous_plugin.write_text("previous plugin bytes\n")
        linked_file = Path(self.env["ORCH_TEST_LINKED_FILE"])
        linked_file.write_text(str(self.plugin_root))
        self._write_fake_git()
        env = self.env | {
            "ORCH_TEST_SOURCE": str(ROOT), "ORCH_TEST_MUTATE_PLUGIN": "1",
        }
        self.write_fail_once_wrapper("ln", "/bin/ln")
        result = self.run_bootstrap("install", env=env, success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(previous_plugin.read_text(), "previous plugin bytes\n")
        self.assertEqual(linked_file.read_text(), str(self.plugin_root))
        self.assertFalse((self.home / ".agents/skills/orch").exists())

    def test_release_plugin_path_change_replaces_owned_cli_link(self):
        self._write_fake_git()
        env = self.env | {"ORCH_TEST_SOURCE": str(ROOT)}
        self.run_bootstrap("install", env=env)
        old_cli_target = os.readlink(self.home / ".local/bin/orch")
        new_plugin = self.root / "new-herdr-plugin/orch"
        new_plugin.mkdir(parents=True)
        shutil.copy2(ROOT / "plugin/herdr-plugin.toml", new_plugin / "herdr-plugin.toml")
        shutil.copy2(ROOT / "plugin/orch", new_plugin / "orch")
        (new_plugin / "orch").chmod(0o755)
        env = env | {"ORCH_TEST_NEW_PLUGIN_ROOT": str(new_plugin)}
        self.run_bootstrap("install", "--repo", "https://github.com/fictional-labs/orch-fork.git", env=env)
        cli = self.home / ".local/bin/orch"
        self.assertNotEqual(os.readlink(cli), old_cli_target)
        self.assertEqual(cli.resolve(), (new_plugin / "orch").resolve())

    def test_failed_release_link_replacement_restores_old_cli_link(self):
        self._write_fake_git()
        env = self.env | {"ORCH_TEST_SOURCE": str(ROOT)}
        self.run_bootstrap("install", env=env)
        cli = self.home / ".local/bin/orch"
        old_target = os.readlink(cli)
        old_plugin_bytes = (self.plugin_root / "orch").read_bytes()
        new_plugin = self.root / "new-herdr-plugin/orch"
        new_plugin.mkdir(parents=True)
        shutil.copy2(ROOT / "plugin/herdr-plugin.toml", new_plugin / "herdr-plugin.toml")
        shutil.copy2(ROOT / "plugin/orch", new_plugin / "orch")
        (new_plugin / "orch").chmod(0o755)
        env = env | {"ORCH_TEST_NEW_PLUGIN_ROOT": str(new_plugin)}
        self.write_fail_once_wrapper("ln", "/bin/ln")
        result = self.run_bootstrap("install", "--repo", "https://github.com/fictional-labs/orch-fork.git", env=env, success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(cli), old_target)
        self.assertEqual(cli.resolve(), (self.plugin_root / "orch").resolve())
        self.assertEqual((self.plugin_root / "orch").read_bytes(), old_plugin_bytes)
        self.assertEqual(Path(self.env["ORCH_TEST_LINKED_FILE"]).read_text(), str(self.plugin_root))

    def test_release_uses_same_repo_and_resolved_ref_for_plugin_install(self):
        self._write_fake_git()
        env = self.env | {"ORCH_TEST_SOURCE": str(ROOT), "ORCH_TEST_GIT_CALLS": str(self.root / "git-calls")}
        self.run_bootstrap("install", "--repo", "https://github.com/fictional-labs/orch-fork.git", "--ref", "v0.1.0", env=env)
        self.assertEqual(self.herdr_mutations()[0]["args"], ["plugin", "install", "fictional-labs/orch-fork/plugin", "--ref", "v0.1.0", "--yes"])
        git_call = json.loads((self.root / "git-calls").read_text())
        self.assertEqual(git_call[:5], ["clone", "--depth", "1", "--branch", "v0.1.0"])
        self.assertEqual(git_call[5], "https://github.com/fictional-labs/orch-fork.git")

    def test_update_fallback_uses_same_repo_and_ref_and_exact_argv(self):
        self._write_fake_git()
        env = self.env | {
            "ORCH_TEST_SOURCE": str(ROOT), "ORCH_TEST_UPDATE_FAIL": "1",
            "ORCH_TEST_GIT_CALLS": str(self.root / "git-calls"),
        }
        self.run_bootstrap("update", "--repo", "https://github.com/fictional-labs/orch-fork.git", env=env)
        self.assertEqual([entry["args"] for entry in self.herdr_mutations()], [
            ["plugin", "update", "fictional-labs/orch-fork/plugin", "--yes"],
            ["plugin", "install", "fictional-labs/orch-fork/plugin", "--ref", "main", "--yes"],
        ])

    def test_update_rejects_unpinnable_custom_ref_before_herdr_mutation(self):
        self._write_fake_git()
        result = self.run_bootstrap("update", "--ref", "v0.1.0", env=self.env | {"ORCH_TEST_SOURCE": str(ROOT)}, success=False)
        self.assertIn("cannot pin --ref", result.stderr)
        self.assert_no_herdr_mutations()

    def test_unsupported_plugin_repository_rejected_before_herdr_mutation(self):
        self._write_fake_git()
        env = self.env | {"ORCH_TEST_SOURCE": str(ROOT)}
        result = self.run_bootstrap("install", "--repo", "https://example.invalid/fictional/orch.git", env=env, success=False)
        self.assertIn("requires a GitHub OWNER/REPO source", result.stderr)
        self.assert_no_herdr_mutations()
        self.assertFalse((self.root / "git-calls").exists())

    def test_home_redirect_applies_home_and_both_xdg_roots_to_herdr(self):
        target_home = self.root / "redirected-home"
        target_home.mkdir()
        env = self.env | {
            "XDG_CONFIG_HOME": str(self.root / "wrong-config"),
            "XDG_STATE_HOME": str(self.root / "wrong-state"),
        }
        self.run_bootstrap("install", "--source", str(ROOT), "--home", str(target_home), env=env)
        self.assertTrue((target_home / ".agents/skills/orch/SKILL.md").is_file())
        self.assertFalse((self.home / ".agents/skills/orch").exists())
        self.assertTrue(self.herdr_mutations())
        for call in self.herdr_mutations():
            self.assertEqual(call["HOME"], str(target_home))
            self.assertEqual(call["XDG_CONFIG_HOME"], str(target_home / ".config"))
            self.assertEqual(call["XDG_STATE_HOME"], str(target_home / ".local/state"))
        for call in self.herdr_env_calls():
            self.assertEqual(call["HOME"], str(target_home))
            self.assertEqual(call["XDG_CONFIG_HOME"], str(target_home / ".config"))
            self.assertEqual(call["XDG_STATE_HOME"], str(target_home / ".local/state"))

    def test_quoted_source_path_marker_is_valid_and_idempotent(self):
        quoted = self.root / 'source"quoted\\line\nnext'
        skill = quoted / "skills/orch"
        skill.parent.mkdir(parents=True)
        shutil.copytree(ROOT / "skills/orch", skill)
        self.run_helper("install", "--source", str(quoted), "--plugin-dir", str(self.plugin_root))
        marker = self.home / ".agents/skills/orch/.orch-install.json"
        parsed = json.loads(marker.read_text())
        self.assertEqual(parsed["source"], str(quoted.resolve()))
        self.run_helper("install", "--source", str(quoted), "--plugin-dir", str(self.plugin_root))
        self.run_helper("check", "--source", str(quoted), "--plugin-dir", str(self.plugin_root))
        self.run_helper("update", "--source", str(quoted), "--plugin-dir", str(self.plugin_root))

    def test_backup_names_are_unique_and_each_archive_is_complete(self):
        self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        date = self.bin / "date"
        date.write_text('#!/bin/sh\nprintf "20261019-120000\\n"\n')
        date.chmod(0o755)
        installed = self.home / ".agents/skills/orch/SKILL.md"
        installed.write_text("first saved version\n")
        self.run_helper("update", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        installed.write_text("second saved version\n")
        self.run_helper("update", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        archives = sorted((self.home / ".agents").glob("orch-backup-*.tgz"))
        self.assertEqual(len(archives), 2)
        saved = []
        for backup in archives:
            with tarfile.open(backup, "r:gz") as archive:
                member = next(m for m in archive.getmembers() if m.name == "orch/SKILL.md")
                saved.append(archive.extractfile(member).read())
        self.assertCountEqual(saved, [b"first saved version\n", b"second saved version\n"])

    def test_failed_backup_archive_is_never_published(self):
        self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        installed = self.home / ".agents/skills/orch/SKILL.md"
        installed.write_text("preserved on backup failure\n")
        failing_tar = self.bin / "tar"
        failing_tar.write_text("#!/bin/sh\nexit 92\n")
        failing_tar.chmod(0o755)
        result = self.run_helper("update", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(installed.read_text(), "preserved on backup failure\n")
        self.assertEqual(list((self.home / ".agents").glob("orch-backup-*.tgz")), [])
        self.assertEqual(list((self.home / ".agents").glob(".orch-backup*")), [])

    def test_backup_publish_does_not_overwrite_racing_archive(self):
        self.run_helper("install", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root))
        installed = self.home / ".agents/skills/orch/SKILL.md"
        installed.write_text("preserved on archive collision\n")
        date = self.bin / "date"
        date.write_text('#!/bin/sh\nprintf "20261019-120000\\n"\n')
        date.chmod(0o755)
        racing_ln = self.bin / "ln"
        racing_ln.write_text('''#!/bin/sh
case "$2" in
  *.tgz) printf 'foreign archive sentinel\\n' > "$2"; exit 93 ;;
esac
exec /bin/ln "$@"
''')
        racing_ln.chmod(0o755)
        result = self.run_helper("update", "--source", str(ROOT), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(installed.read_text(), "preserved on archive collision\n")
        archives = list((self.home / ".agents").glob("orch-backup-*.tgz"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), b"foreign archive sentinel\n")
        self.assertEqual(list((self.home / ".agents").glob(".orch-backup*")), [])

    def test_incomplete_skill_is_rejected_before_writes_or_herdr_mutations(self):
        incomplete = self.root / "incomplete"
        shutil.copytree(ROOT / "skills/orch", incomplete / "skills/orch")
        (incomplete / "skills/orch/commands/close.md").unlink()
        before = self.tree_snapshot(self.home)
        result = self.run_helper("install", "--source", str(incomplete), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertIn("incomplete orch skill source", result.stderr)
        self.assertEqual(self.tree_snapshot(self.home), before)
        self.assert_no_herdr_mutations()

    def test_missing_referenced_skill_resource_is_rejected_before_writes(self):
        incomplete = self.root / "missing-resource"
        shutil.copytree(ROOT / "skills/orch", incomplete / "skills/orch")
        skill_doc = incomplete / "skills/orch/SKILL.md"
        skill_doc.write_text(skill_doc.read_text() + "\nSee [missing guide](references/absent.md).\n")
        before = self.tree_snapshot(self.home)
        result = self.run_helper("install", "--source", str(incomplete), "--plugin-dir", str(self.plugin_root), success=False)
        self.assertIn("references missing references/absent.md", result.stderr)
        self.assertEqual(self.tree_snapshot(self.home), before)

    def test_bootstrap_incomplete_skill_rejected_before_herdr_mutation(self):
        incomplete = self.root / "incomplete-repo"
        (incomplete / "skills/orch/commands").mkdir(parents=True)
        shutil.copy2(ROOT / "skills/orch/SKILL.md", incomplete / "skills/orch/SKILL.md")
        shutil.copytree(ROOT / "plugin", incomplete / "plugin")
        shutil.copytree(ROOT / "scripts", incomplete / "scripts")
        result = self.run_bootstrap("install", "--source", str(incomplete), success=False)
        self.assertIn("incomplete orch skill source", result.stderr)
        self.assert_no_herdr_mutations()
        self.assertEqual(self.herdr_calls(), [])

    def test_herdr_destination_ancestor_rejected_before_mutation(self):
        (self.home / ".config").write_text("blocked\n")
        result = self.run_bootstrap("install", "--source", str(ROOT), success=False)
        self.assertIn("Herdr destination ancestor is not a directory", result.stderr)
        self.assert_no_herdr_mutations()
        self.assertEqual(self.herdr_calls(), [])

    def test_workflow_pins_verified_actions_and_python_minimum(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", workflow)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", workflow)
        self.assertIn("python-version: '3.11'", workflow)


if __name__ == "__main__":
    unittest.main()
