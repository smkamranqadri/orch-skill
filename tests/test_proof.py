import hashlib
import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock

import tests.test_phase1 as phase1
import tests.test_phase2 as phase2

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin" / "orch"
sys.path.insert(0, str(ROOT / "plugin"))
import orchlib
from plugin import board

SESSION = phase2.SESSION
ORCH = phase2.ORCH
GOOD_CMD = 'test "$(cat value.txt)" = good'
ALPHA = "alpha-guard | tests/test_alpha.py | tripped=True | restored byte-identical=True"
BETA = "beta-guard | tests/test_beta.py | tripped=True | restored byte-identical=True"
FIXTURES = ROOT / "tests" / "fixtures"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run_git(env, tree, *args, check=True):
    return subprocess.run(["git", "-C", str(tree), *args], env=env, text=True, capture_output=True, check=check)


def write_build_proof(env, tree, name, *, guards="alpha-guard,beta-guard", mutations=(ALPHA, BETA), log_lines=("fictional tests ok",),
                      exit_line="exit=0", skip=(), overrides=None):
    """Valid build proof for the current tree, with named parts broken on request."""
    base = pathlib.Path(tree) / ".orch" / name
    base.mkdir(parents=True, exist_ok=True)
    log = base / "run-1.log"
    log.write_text("".join(line + "\n" for line in (*log_lines, exit_line)))
    mutation_log = base / "mutations.log"
    mutation_log.write_text("".join(line + "\n" for line in mutations))
    with mock.patch.dict(os.environ, env):
        fingerprint = orchlib.fingerprint(tree)
    fields = {"run_log": str(log), "run_sha256": sha256(log.read_bytes()), "tree_fingerprint": fingerprint,
              "mutations_log": str(mutation_log), "guards": guards}
    fields.update(overrides or {})
    (base / "handoff.md").write_text("".join(f"{key}: {value}\n" for key, value in fields.items() if key not in skip) + "\nFictional notes.\n")
    return fields


REPRO_HEAD = '#!/bin/sh\nchecked="$(cat "$1/value.txt")"\n'
REPRO_OK = REPRO_HEAD + (
    'echo "F1 expected=good observed=$checked"\n'
    'if [ "$checked" = good ]; then echo "F1 NOT-REPRODUCED"; else echo "F1 REPRODUCED"; fi\n')


def write_review_proof(tree, name, *, findings="F1", review_extra="", repro=REPRO_OK, executable=True, skip_repro=False, skip_review=False):
    base = pathlib.Path(tree) / ".orch" / name
    base.mkdir(parents=True, exist_ok=True)
    if not skip_review:
        (base / "review.md").write_text(f"findings: {findings}\n{review_extra}\nFictional review notes.\n")
    if not skip_repro:
        (base / "repro.sh").write_text(repro)
        (base / "repro.sh").chmod(0o755 if executable else 0o644)
    return base


def tree_files(tree):
    out = {}
    for path in sorted(pathlib.Path(tree).rglob("*")):
        rel = path.relative_to(tree).as_posix()
        if rel == ".git" or (rel.startswith(".orch/") and "/verify-clean-" in rel):
            continue
        if path.is_symlink():
            out[rel] = ("link", os.readlink(path), path.lstat().st_mode)
        elif path.is_file():
            out[rel] = ("file", path.read_bytes(), path.lstat().st_mode)
        else:
            out[rel] = ("dir", None, None)
    return out


class Fixtures:
    """Helpers shared by the harness-bound test classes below."""

    def git(self, tree, *args, check=True):
        return run_git(self.env, tree, *args, check=check)

    def patch_environment(self):
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        ttl = mock.patch.object(orchlib, "LIVE_FP_TTL", 0)
        ttl.start()
        self.addCleanup(ttl.stop)

    def new_checkout(self, name, value="good\n"):
        path = self.root / f"{name}.wt"
        self.git(self.repo, "worktree", "add", "-qb", f"orch/{name}", str(path))
        (path / "value.txt").write_text(value)
        (path / "bin.dat").write_bytes(bytes(range(16)))
        (path / "tool.sh").write_text("echo fictional tool\n")
        os.symlink("value.txt", path / "link")
        self.git(path, "add", "-A")
        self.git(path, "commit", "-qm", "fixture files")
        orchlib.ensure_excluded(path)
        return path

    def add_row(self, name, role, tree, test_cmd=GOOD_CMD, **extra):
        data = self.registry()
        row = {"name": name, "pane": f"w2:p{len(data['agents']) + 20}", "orch": ORCH, "project": str(self.repo), "kind": "claude",
               "role": role, "where": "worktree", "writes": role == "build", "tree": str(tree), "branch": f"orch/{name}",
               "worktree": None, "created": [], "state": "live", "status": "idle", "since": int(time.time()), "started": True,
               "stopped": False, "agent_closed": False, "pane_closed": False, "proof": 1, "proof_id": uuid.uuid4().hex,
               "test_cmd": test_cmd}
        row.update(extra)
        data["agents"][f"{SESSION}/{name}"] = row
        self.registry_path.write_text(json.dumps(data))
        return row

    def good_build(self, name, **proof):
        tree = self.new_checkout(name)
        row = self.add_row(name, "build", tree)
        return tree, row, write_build_proof(self.env, tree, name, **proof)

    def verify(self, name, *args, env=None):
        result = subprocess.run([str(CLI), "verify", name, *args], cwd=self.repo, env=env or self.env, text=True, capture_output=True, timeout=60)
        return result, result.stdout.splitlines()

    @staticmethod
    def fails(lines):
        return [line for line in lines if line.startswith("FAIL ")]

    def prime(self, tree):
        self.git(tree, "status", "--porcelain", "--ignored")

    def tree_state(self, tree):
        self.prime(tree)
        state = {key: self.git(tree, *args).stdout for key, args in (
            ("head", ("rev-parse", "HEAD")), ("branch", ("symbolic-ref", "HEAD")), ("status", ("status", "--porcelain=v2", "--ignored")),
            ("worktrees", ("worktree", "list", "--porcelain")), ("refs", ("for-each-ref",)))}
        state["stash"] = self.git(self.repo, "stash", "list").stdout
        index = pathlib.Path(self.git(tree, "rev-parse", "--git-path", "index").stdout.strip())
        state["index"] = (index if index.is_absolute() else pathlib.Path(tree) / index).read_bytes()
        state["files"] = tree_files(tree)
        return state


class Phase2Harness:
    """Borrows the phase 2 fixture (fake Herdr, registry, hook runner) without inheriting its tests."""
    setUp = phase2.PhaseTwo.setUp
    tearDown = phase2.PhaseTwo.tearDown
    registry = phase2.PhaseTwo.registry
    write_registry = phase2.PhaseTwo.write_registry
    write_herdr_state = phase2.PhaseTwo.write_herdr_state
    run_hook = phase2.PhaseTwo.run_hook
    set_sequence_worker = phase2.PhaseTwo.set_sequence_worker
    wait_for_worker_status = phase2.PhaseTwo.wait_for_worker_status
    status_event = phase2.PhaseTwo.status_event


class ProofVerifyTests(Phase2Harness, Fixtures, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.patch_environment()

    def test_correct_build_fixture_passes_and_stores_a_bound_verdict(self):
        tree, row, fields = self.good_build("quartz-proof")
        result, lines = self.verify("quartz-proof")
        log = tree / ".orch" / "quartz-proof" / "verify-clean-1.log"
        self.assertEqual(lines, [
            "PASS handoff has every field", "PASS run_sha256 matches the run log", "PASS run log ends with exit=0",
            "PASS tree_fingerprint unchanged", "PASS guard alpha-guard tripped and restored byte-identical",
            "PASS guard beta-guard tripped and restored byte-identical", f"PASS clean run exit=0 (log {log})", "RESULT: PASS"])
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = self.registry()["agents"][f"{SESSION}/quartz-proof"]["verdict"]
        self.assertEqual(saved["result"], "passing")
        self.assertEqual(saved["binding"]["test_cmd"], GOOD_CMD)
        self.assertEqual(saved["binding"]["fingerprint"], fields["tree_fingerprint"])
        self.assertRegex(saved["binding"]["digest"], r"^[0-9a-f]{64}$")

    def test_guards_none_with_empty_log_passes(self):
        self.good_build("quartz-none", guards="none", mutations=())
        result, lines = self.verify("quartz-none")
        self.assertIn("PASS no guards declared", lines)
        self.assertEqual(lines[-1], "RESULT: PASS")

    def test_missing_handoff_fails_with_anchored_line(self):
        tree = self.new_checkout("quartz-nohandoff")
        self.add_row("quartz-nohandoff", "build", tree)
        result, lines = self.verify("quartz-nohandoff")
        self.assertEqual(lines, [f"FAIL handoff missing or unreadable: {tree / '.orch' / 'quartz-nohandoff' / 'handoff.md'}", "RESULT: FAIL (1)"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.registry()["agents"][f"{SESSION}/quartz-nohandoff"]["verdict"]["result"], "failing")

    def test_each_missing_handoff_field_fails_by_name(self):
        for field in ("run_log", "run_sha256", "tree_fingerprint", "mutations_log", "guards"):
            with self.subTest(field=field):
                name = "quartz-" + field.replace("_", "-")
                tree = self.new_checkout(name)
                self.add_row(name, "build", tree)
                write_build_proof(self.env, tree, name, skip=(field,))
                result, lines = self.verify(name)
                self.assertEqual(lines, [f"FAIL handoff missing field {field}", "RESULT: FAIL (1)"])

    def test_missing_run_log_fails(self):
        tree, row, fields = self.good_build("quartz-nolog")
        pathlib.Path(fields["run_log"]).unlink()
        result, lines = self.verify("quartz-nolog")
        self.assertEqual(self.fails(lines), [f"FAIL run_log missing: {fields['run_log']}"])

    def test_run_log_outside_the_proof_dir_fails(self):
        tree = self.new_checkout("quartz-outside")
        self.add_row("quartz-outside", "build", tree)
        outside = self.root / "elsewhere.log"
        outside.write_text("fictional\nexit=0\n")
        write_build_proof(self.env, tree, "quartz-outside", overrides={"run_log": str(outside), "run_sha256": sha256(outside.read_bytes())})
        result, lines = self.verify("quartz-outside")
        self.assertEqual(self.fails(lines), [f"FAIL run_log outside the proof dir: {outside}"])

    def test_hash_mismatch_fails(self):
        tree, row, fields = self.good_build("quartz-hash")
        log = pathlib.Path(fields["run_log"])
        log.write_text("tampered line\nexit=0\n")
        result, lines = self.verify("quartz-hash")
        self.assertEqual(self.fails(lines), ["FAIL run_sha256 does not match the run log"])

    def test_last_line_not_exit_zero_fails(self):
        tree = self.new_checkout("quartz-exit")
        self.add_row("quartz-exit", "build", tree)
        write_build_proof(self.env, tree, "quartz-exit", exit_line="exit=1")
        result, lines = self.verify("quartz-exit")
        self.assertEqual(self.fails(lines), ["FAIL run log does not end with exit=0"])

    def test_fingerprint_changes_fail_for_each_kind_of_edit(self):
        def new_commit(tree):
            (tree / "extra.txt").write_text("committed\n")
            self.git(tree, "add", "extra.txt")
            self.git(tree, "commit", "-qm", "later commit")

        def staged_edit(tree):
            (tree / "value.txt").write_text("good staged\n")
            self.git(tree, "add", "value.txt")

        def unstaged_edit(tree):
            (tree / "value.txt").write_text("good unstaged\n")

        def added_file(tree):
            (tree / "added.txt").write_text("added\n")

        def deleted_file(tree):
            (tree / "tool.sh").unlink()

        def binary_change(tree):
            (tree / "bin.dat").write_bytes(bytes(reversed(range(16))))

        def mode_change(tree):
            (tree / "tool.sh").chmod(0o755)

        def symlink_change(tree):
            (tree / "link").unlink()
            os.symlink("tool.sh", tree / "link")

        for index, change in enumerate((new_commit, staged_edit, unstaged_edit, added_file, deleted_file, binary_change, mode_change, symlink_change)):
            with self.subTest(change=change.__name__):
                name = f"quartz-fp-{index}"
                tree, row, fields = self.good_build(name)
                change(tree)
                result, lines = self.verify(name)
                self.assertEqual(self.fails(lines), ["FAIL tree_fingerprint changed since the final run"])
                self.assertEqual(result.returncode, 1)

    def test_malformed_and_truncated_mutation_records_fail(self):
        cases = {
            "garbage": ["not a record"],
            "truncated": [ALPHA, "beta-guard | tests/test_beta.py | tripped=True"],
            "wrongcase": [ALPHA, "beta-guard | tests/test_beta.py | tripped=true | restored byte-identical=True"],
        }
        for label, records in cases.items():
            with self.subTest(label=label):
                name = f"quartz-mut-{label}"
                tree = self.new_checkout(name)
                self.add_row(name, "build", tree)
                write_build_proof(self.env, tree, name, mutations=records)
                result, lines = self.verify(name)
                bad = len(records)
                expected = [f"FAIL mutations.log line {bad} is malformed"]
                if label == "garbage":
                    expected += ["FAIL guard alpha-guard has no mutation record", "FAIL guard beta-guard has no mutation record"]
                else:
                    expected += ["FAIL guard beta-guard has no mutation record"]
                self.assertEqual(self.fails(lines), expected)

    def test_declared_guard_without_record_and_undeclared_record_fail(self):
        tree = self.new_checkout("quartz-guards")
        self.add_row("quartz-guards", "build", tree)
        write_build_proof(self.env, tree, "quartz-guards", guards="alpha-guard,gamma-guard", mutations=(ALPHA, BETA))
        result, lines = self.verify("quartz-guards")
        self.assertEqual(self.fails(lines), ["FAIL guard beta-guard has a record but is not declared in guards",
                                             "FAIL guard gamma-guard has no mutation record"])

    def test_latest_record_decides_in_both_append_orders(self):
        broken = "alpha-guard | tests/test_alpha.py | tripped=False | restored byte-identical=True"
        unrestored = "alpha-guard | tests/test_alpha.py | tripped=True | restored byte-identical=False"
        cases = (
            ("later-untripped", (ALPHA, broken), ["FAIL guard alpha-guard latest record has tripped=False"]),
            ("later-unrestored", (ALPHA, unrestored), ["FAIL guard alpha-guard latest record has restored byte-identical=False"]),
            ("fixed-after-untripped", (broken, ALPHA), []),
            ("fixed-after-unrestored", (unrestored, ALPHA), []),
        )
        for label, records, expected in cases:
            with self.subTest(label=label):
                name = f"quartz-latest-{label}"
                tree = self.new_checkout(name)
                self.add_row(name, "build", tree)
                write_build_proof(self.env, tree, name, guards="alpha-guard", mutations=records)
                result, lines = self.verify(name)
                self.assertEqual(self.fails(lines), expected)

    def test_clean_run_tests_the_dirty_tree_and_leaves_the_worker_untouched(self):
        tree = self.new_checkout("quartz-dirty")
        (tree / "value.txt").write_text("bad\n")
        (tree / "extra.txt").write_text("untracked\n")
        self.add_row("quartz-dirty", "build", tree, test_cmd='pwd; cat value.txt extra.txt; test "$(cat value.txt)" = good')
        write_build_proof(self.env, tree, "quartz-dirty")
        before = self.tree_state(tree)
        result, lines = self.verify("quartz-dirty")
        log = tree / ".orch" / "quartz-dirty" / "verify-clean-1.log"
        self.assertEqual(self.fails(lines), [f"FAIL clean run exit=1 (log {log})"])
        self.assertEqual(lines[-1], "RESULT: FAIL (1)")
        seen = log.read_text().splitlines()
        self.assertEqual(seen[1:], ["bad", "untracked"])
        self.assertNotEqual(seen[0], str(tree))
        self.assertTrue(seen[0].startswith(str(self.root / "orch-verify-")), seen[0])
        self.assertEqual(self.tree_state(tree), before)
        self.assertEqual([path.name for path in self.root.glob("orch-verify-*")], [])

    def test_interrupt_during_clean_run_removes_the_snapshot_and_writes_no_verdict(self):
        tree = self.new_checkout("quartz-interrupt")
        marker = self.root / "started"
        pidfile = self.root / "child.pid"
        self.add_row("quartz-interrupt", "build", tree, test_cmd=f"echo $$ > {pidfile}; touch {marker}; sleep 30")
        write_build_proof(self.env, tree, "quartz-interrupt")
        before = self.git(tree, "worktree", "list").stdout
        process = subprocess.Popen([str(CLI), "verify", "quartz-interrupt"], cwd=self.repo, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())
        self.assertNotEqual(self.git(tree, "worktree", "list").stdout, before)
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.git(tree, "worktree", "list").stdout, before)
        self.assertEqual([path.name for path in self.root.glob("orch-verify-*")], [])
        self.assertNotIn("verdict", self.registry()["agents"][f"{SESSION}/quartz-interrupt"])
        child = int(pidfile.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_slow_verify_does_not_block_other_registry_commands(self):
        tree = self.new_checkout("quartz-slow")
        marker = self.root / "slow-started"
        self.add_row("quartz-slow", "build", tree, test_cmd=f"touch {marker}; sleep 3")
        write_build_proof(self.env, tree, "quartz-slow")
        process = subprocess.Popen([str(CLI), "verify", "quartz-slow"], cwd=self.repo, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())
        started = time.monotonic()
        listed = subprocess.run([str(CLI), "list"], cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=1.5)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertIsNone(process.poll(), "verify finished before the registry command ran")
        process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0)

    def test_name_reuse_or_close_during_verify_writes_no_verdict(self):
        for label in ("replaced", "closed"):
            with self.subTest(label=label):
                name = f"quartz-{label}"
                tree = self.new_checkout(name)
                marker = self.root / f"{label}-started"
                self.add_row(name, "build", tree, test_cmd=f"touch {marker}; sleep 1")
                write_build_proof(self.env, tree, name)
                process = subprocess.Popen([str(CLI), "verify", name], cwd=self.repo, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                deadline = time.monotonic() + 20
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists())
                data = self.registry()
                key = f"{SESSION}/{name}"
                if label == "replaced":
                    data["agents"][key] = dict(data["agents"][key], proof_id=uuid.uuid4().hex, since=data["agents"][key]["since"] + 5)
                else:
                    data["agents"][key].update(state="closed", status="closed", agent_closed=True)
                self.registry_path.write_text(json.dumps(data))
                stdout, stderr = process.communicate(timeout=30)
                self.assertIn("FAIL row changed during verify", stdout.splitlines())
                self.assertEqual(stdout.splitlines()[-1], "RESULT: FAIL (1)")
                self.assertNotIn("verdict", self.registry()["agents"][key])

    def test_proof_edited_during_verify_writes_no_verdict(self):
        tree = self.new_checkout("quartz-edited")
        marker = self.root / "edited-started"
        self.add_row("quartz-edited", "build", tree, test_cmd=f"touch {marker}; sleep 1")
        fields = write_build_proof(self.env, tree, "quartz-edited")
        process = subprocess.Popen([str(CLI), "verify", "quartz-edited"], cwd=self.repo, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())
        handoff = tree / ".orch" / "quartz-edited" / "handoff.md"
        handoff.write_text(handoff.read_text() + "late_note: edited during verify\n")
        stdout, stderr = process.communicate(timeout=30)
        self.assertIn("FAIL row changed during verify", stdout.splitlines())
        self.assertNotIn("verdict", self.registry()["agents"][f"{SESSION}/quartz-edited"])

    def test_failing_verdict_is_stored_with_its_binding(self):
        tree = self.new_checkout("quartz-failing")
        self.add_row("quartz-failing", "build", tree)
        write_build_proof(self.env, tree, "quartz-failing", exit_line="exit=2")
        result, lines = self.verify("quartz-failing")
        self.assertEqual(result.returncode, 1)
        verdict = self.registry()["agents"][f"{SESSION}/quartz-failing"]["verdict"]
        self.assertEqual(verdict["result"], "failing")
        self.assertEqual(sorted(verdict["binding"]), ["digest", "fingerprint", "test_cmd"])

    def test_legacy_rows_have_no_proof_protocol(self):
        tree = self.new_checkout("quartz-legacy")
        self.add_row("quartz-legacy", "build", tree)
        data = self.registry()
        data["agents"][f"{SESSION}/quartz-legacy"].pop("proof")
        self.registry_path.write_text(json.dumps(data))
        result, lines = self.verify("quartz-legacy")
        self.assertEqual(lines, ["FAIL no proof protocol on this row", "RESULT: FAIL (1)"])
        self.assertEqual(result.returncode, 1)
        for role in ("plan", "explore"):
            self.add_row(f"quartz-{role}", role, tree)
            data = self.registry()
            data["agents"][f"{SESSION}/quartz-{role}"]["proof"] = 1
            self.registry_path.write_text(json.dumps(data))
            result, lines = self.verify(f"quartz-{role}")
            self.assertEqual(lines, ["FAIL no proof protocol on this row", "RESULT: FAIL (1)"])

    def test_closed_row_and_unknown_row_are_refused(self):
        tree, row, fields = self.good_build("quartz-gone")
        data = self.registry()
        data["agents"][f"{SESSION}/quartz-gone"].update(state="closed", status="closed", agent_closed=True)
        self.registry_path.write_text(json.dumps(data))
        result, lines = self.verify("quartz-gone")
        self.assertEqual(lines, ["FAIL agent is closed", "RESULT: FAIL (1)"])
        result, lines = self.verify("quartz-unknown")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown agent: quartz-unknown", result.stderr)

    def test_clean_run_includes_staged_ignored_files_and_keeps_the_worker_index(self):
        tree = self.new_checkout("quartz-staged")
        (tree / ".gitignore").write_text("trigger.txt\n")
        self.git(tree, "add", ".gitignore")
        (tree / "trigger.txt").write_text("staged only\n")
        self.git(tree, "add", "-f", "trigger.txt")
        self.add_row("quartz-staged", "build", tree, test_cmd="test ! -f trigger.txt")
        write_build_proof(self.env, tree, "quartz-staged")
        before = self.tree_state(tree)
        result, lines = self.verify("quartz-staged")
        log = tree / ".orch" / "quartz-staged" / "verify-clean-1.log"
        self.assertEqual(self.fails(lines), [f"FAIL clean run exit=1 (log {log})"])
        self.assertEqual(self.tree_state(tree), before)

    def test_verdict_stops_binding_to_a_live_tree_that_changed(self):
        tree, row, fields = self.good_build("quartz-fresh")
        self.assertEqual(self.verify("quartz-fresh")[0].returncode, 0)
        saved = self.registry()["agents"][f"{SESSION}/quartz-fresh"]
        self.assertEqual(orchlib.proof_state(saved), "passing")
        (tree / "value.txt").write_text("changed after verify\n")
        self.assertEqual(orchlib.proof_state(saved), "present")

    def test_verdict_binds_the_bytes_of_the_files_the_handoff_names(self):
        tree = self.new_checkout("quartz-alt")
        self.add_row("quartz-alt", "build", tree)
        base = tree / ".orch" / "quartz-alt"
        write_build_proof(self.env, tree, "quartz-alt", overrides={"mutations_log": str(base / "round-two.log")})
        (base / "mutations.log").rename(base / "round-two.log")
        self.assertEqual(self.verify("quartz-alt")[0].returncode, 0)
        saved = self.registry()["agents"][f"{SESSION}/quartz-alt"]
        self.assertEqual(orchlib.proof_state(saved), "passing")
        (base / "round-two.log").write_text(ALPHA.replace("tripped=True", "tripped=False") + "\n" + BETA + "\n")
        self.assertEqual(orchlib.proof_state(saved), "present")
        result, lines = self.verify("quartz-alt")
        self.assertEqual(self.fails(lines), ["FAIL guard alpha-guard latest record has tripped=False"])

    def test_verdict_binds_run_log_bytes_even_when_size_and_mtime_are_restored(self):
        tree, row, fields = self.good_build("quartz-bytes")
        self.assertEqual(self.verify("quartz-bytes")[0].returncode, 0)
        saved = self.registry()["agents"][f"{SESSION}/quartz-bytes"]
        log = pathlib.Path(fields["run_log"])
        before = log.stat()
        log.write_bytes(log.read_bytes().replace(b"exit=0", b"exit=1"))
        os.utime(log, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual((log.stat().st_size, log.stat().st_mtime_ns), (before.st_size, before.st_mtime_ns))
        self.assertEqual(orchlib.proof_state(saved), "present")
        result, lines = self.verify("quartz-bytes")
        self.assertEqual(self.fails(lines), ["FAIL run_sha256 does not match the run log", "FAIL run log does not end with exit=0"])

    def test_tree_edit_during_verify_writes_no_verdict(self):
        tree = self.new_checkout("quartz-tree-edit")
        marker = self.root / "tree-edit-started"
        self.add_row("quartz-tree-edit", "build", tree, test_cmd=f"touch {marker}; sleep 1")
        write_build_proof(self.env, tree, "quartz-tree-edit")
        process = subprocess.Popen([str(CLI), "verify", "quartz-tree-edit"], cwd=self.repo, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())
        (tree / "value.txt").write_text("edited while the clean run was going\n")
        stdout, stderr = process.communicate(timeout=30)
        self.assertIn("FAIL row changed during verify", stdout.splitlines())
        self.assertNotIn("verdict", self.registry()["agents"][f"{SESSION}/quartz-tree-edit"])

    def test_symlinked_proof_dir_is_refused_by_verify(self):
        tree = self.new_checkout("quartz-link")
        self.add_row("quartz-link", "build", tree)
        external = self.root / "external-proof"
        external.mkdir()
        (tree / ".orch").mkdir(exist_ok=True)
        os.symlink(external, tree / ".orch" / "quartz-link")
        result, lines = self.verify("quartz-link")
        self.assertEqual(lines, [f"FAIL proof dir refused; {tree / '.orch' / 'quartz-link'} is a symlink", "RESULT: FAIL (1)"])

    def test_timeout_kills_descendants_even_when_the_script_already_exited(self):
        pidfile = self.root / "orphan.pid"
        script = f'#!/bin/sh\nsleep 30 &\necho $! > "{pidfile}"\nexit 0\n'
        target, base = self.review_row("maple-orphan", repro=script)
        result, lines = self.verify("maple-orphan", "--against", str(target), env=self.env | {"ORCH_REPRO_TIMEOUT": "0.3"})
        self.assertEqual(self.fails(lines), ["FAIL repro.sh timed out after 0.3s"])
        child = int(pidfile.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_any_f_digit_line_that_is_not_well_formed_fails(self):
        cases = {
            "tab": ("none", '#!/bin/sh\nprintf "F1\\tREPRODUCED\\n"\n', "F1\tREPRODUCED"),
            "glued": ("F1", REPRO_OK + 'echo "F1REPRODUCED"\n', "F1REPRODUCED"),
            "bare": ("none", '#!/bin/sh\necho "F2"\n', "F2"),
        }
        for label, (findings, script, line) in cases.items():
            with self.subTest(label=label):
                target, base = self.review_row(f"maple-shape-{label}", findings=findings, repro=script)
                result, lines = self.verify(f"maple-shape-{label}", "--against", str(target))
                self.assertEqual(self.fails(lines), [f"FAIL malformed repro line: {line}"])
                self.assertEqual(result.returncode, 1)

    # Reviews

    def review_row(self, name, **proof):
        target = self.new_checkout(name + "-target", value="bad\n")
        base = write_review_proof(self.repo, name, **proof)
        self.add_row(name, "review", self.repo, test_cmd=None, where="pane", branch=None)
        return target, base

    def test_review_fixture_passes_against_the_reviewed_tree(self):
        target, base = self.review_row("maple-review")
        result, lines = self.verify("maple-review", "--against", str(target))
        self.assertEqual(lines, ["PASS F1 REPRODUCED", "RESULT: PASS"])
        verdict = self.registry()["agents"][f"{SESSION}/maple-review"]["verdict"]
        self.assertEqual(verdict["result"], "passing")
        self.assertEqual(verdict["binding"]["against"], str(target))
        self.assertEqual(verdict["binding"]["want"], "REPRODUCED")

    def test_fixed_tree_passes_with_want_not_reproduced_and_fails_by_default(self):
        target, base = self.review_row("maple-fixed")
        (target / "value.txt").write_text("good\n")
        result, lines = self.verify("maple-fixed", "--against", str(target), "--want", "NOT-REPRODUCED")
        self.assertEqual(lines, ["PASS F1 NOT-REPRODUCED", "RESULT: PASS"])
        result, lines = self.verify("maple-fixed", "--against", str(target))
        self.assertEqual(self.fails(lines), ["FAIL F1 is NOT-REPRODUCED, wanted REPRODUCED"])

    def test_findings_none_passes_and_manual_is_reported_without_failing(self):
        target, base = self.review_row("maple-none", findings="none", repro="#!/bin/sh\nexit 0\n")
        result, lines = self.verify("maple-none", "--against", str(target))
        self.assertEqual(lines, ["PASS no findings declared", "RESULT: PASS"])
        manual = REPRO_HEAD + 'echo "F1 expected=a person observes observed=n/a"\necho "F1 MANUAL"\n'
        target, base = self.review_row("maple-manual", repro=manual, review_extra="F1 manual: needs a human to judge tone")
        result, lines = self.verify("maple-manual", "--against", str(target))
        self.assertEqual(lines, ["MANUAL F1 needs a person: needs a human to judge tone", "RESULT: PASS"])
        self.assertEqual(result.returncode, 0)
        target, base = self.review_row("maple-noreason", repro=manual)
        result, lines = self.verify("maple-noreason", "--against", str(target))
        self.assertEqual(self.fails(lines), ["FAIL F1 is MANUAL without a reason in review.md"])

    def test_repro_failures_are_anchored(self):
        evidence = 'echo "F1 expected=good observed=bad"\n'
        cases = {
            "nonzero": (REPRO_OK + "exit 3\n", {}, ["FAIL repro.sh exited 3"]),
            "timeout": ("#!/bin/sh\nsleep 8\n", {"ORCH_REPRO_TIMEOUT": "1"}, ["FAIL repro.sh timed out after 1s"]),
            "missing": ("#!/bin/sh\nexit 0\n", {}, ["FAIL F1 has no result line"]),
            "duplicate": (REPRO_HEAD + evidence + 'echo "F1 REPRODUCED"\necho "F1 REPRODUCED"\n', {}, ["FAIL F1 has 2 result lines"]),
            "undeclared": (REPRO_OK + 'echo "F2 expected=a observed=b"\necho "F2 REPRODUCED"\n', {}, ["FAIL F2 is not declared in findings"]),
            "noevidence": (REPRO_HEAD + 'echo "F1 REPRODUCED"\n', {}, ["FAIL F1 has no expected/observed evidence line"]),
            "malformed": (REPRO_OK + 'echo "F1 MAYBE"\n', {}, ["FAIL malformed repro line: F1 MAYBE"]),
        }
        for label, (script, extra_env, expected) in cases.items():
            with self.subTest(label=label):
                target, base = self.review_row(f"maple-{label}", repro=script)
                result, lines = self.verify(f"maple-{label}", "--against", str(target), env=self.env | extra_env)
                self.assertEqual(self.fails(lines), expected)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.registry()["agents"][f"{SESSION}/maple-{label}"]["verdict"]["result"], "failing")

    def test_review_proof_files_missing_or_not_executable_fail(self):
        target, base = self.review_row("maple-norepro", skip_repro=True)
        result, lines = self.verify("maple-norepro", "--against", str(target))
        self.assertEqual(self.fails(lines), [f"FAIL repro.sh missing or not an executable file: {base / 'repro.sh'}"])
        target, base = self.review_row("maple-plain", executable=False)
        result, lines = self.verify("maple-plain", "--against", str(target))
        self.assertEqual(self.fails(lines), [f"FAIL repro.sh missing or not an executable file: {base / 'repro.sh'}"])
        target, base = self.review_row("maple-noreview", skip_review=True)
        result, lines = self.verify("maple-noreview", "--against", str(target))
        self.assertEqual(self.fails(lines), [f"FAIL review.md missing or unreadable: {base / 'review.md'}"])
        target, base = self.review_row("maple-badfindings", findings="F1;F2")
        result, lines = self.verify("maple-badfindings", "--against", str(target))
        self.assertEqual(self.fails(lines), ["FAIL review.md has no valid findings: line"])

    def test_review_requires_against_and_build_refuses_it(self):
        target, base = self.review_row("maple-needs")
        result, lines = self.verify("maple-needs")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--against is required for a review row", result.stderr)
        self.assertEqual(lines, [])
        tree, row, fields = self.good_build("quartz-against")
        result, lines = self.verify("quartz-against", "--against", str(tree))
        self.assertEqual(lines, ["FAIL --against applies to review rows only", "RESULT: FAIL (1)"])

    def test_repro_runs_with_the_checkout_as_cwd_and_argument(self):
        script = '#!/bin/sh\necho "F1 expected=$1 observed=$(pwd -P)"\nif [ "$1" = "$(pwd -P)" ]; then echo "F1 REPRODUCED"; else echo "F1 NOT-REPRODUCED"; fi\n'
        target, base = self.review_row("maple-cwd", repro=script)
        result, lines = self.verify("maple-cwd", "--against", str(target))
        self.assertEqual(lines, ["PASS F1 REPRODUCED", "RESULT: PASS"])


class ProofFingerprintTests(Phase2Harness, Fixtures, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.patch_environment()

    def test_fingerprint_is_deterministic_and_hex(self):
        first = self.new_checkout("quartz-fp-a")
        second = self.new_checkout("quartz-fp-b")
        self.assertRegex(orchlib.fingerprint(first), r"^[0-9a-f]{64}$")
        self.assertEqual(orchlib.fingerprint(first), orchlib.fingerprint(second))

    def test_untracked_content_mode_and_symlink_target_are_hashed(self):
        tree = self.new_checkout("quartz-fp-untracked")
        (tree / "new.txt").write_text("one\n")
        base = orchlib.fingerprint(tree)
        (tree / "new.txt").write_text("two\n")
        content = orchlib.fingerprint(tree)
        (tree / "new.txt").chmod(0o755)
        mode = orchlib.fingerprint(tree)
        (tree / "new.txt").unlink()
        os.symlink("one", tree / "new.txt")
        link_one = orchlib.fingerprint(tree)
        (tree / "new.txt").unlink()
        os.symlink("two", tree / "new.txt")
        link_two = orchlib.fingerprint(tree)
        self.assertEqual(len({base, content, mode, link_one, link_two}), 5)

    def test_proof_files_never_enter_the_fingerprint_or_the_status(self):
        tree = self.new_checkout("quartz-fp-proof")
        before = orchlib.fingerprint(tree)
        write_build_proof(self.env, tree, "quartz-fp-proof")
        (tree / ".orch" / "other").mkdir()
        (tree / ".orch" / "other" / "note.txt").write_text("scratch\n")
        self.assertEqual(orchlib.fingerprint(tree), before)
        self.assertEqual(self.git(tree, "status", "--porcelain").stdout, "")

    def test_git_and_read_errors_are_failures_not_empty_hashes(self):
        with self.assertRaises(RuntimeError):
            orchlib.fingerprint(self.root / "not-a-repository")
        tree = self.new_checkout("quartz-fp-errors")
        secret = tree / "unreadable.txt"
        secret.write_text("hidden\n")
        secret.chmod(0)
        try:
            with self.assertRaises(RuntimeError):
                orchlib.fingerprint(tree)
        finally:
            secret.chmod(0o644)
        secret.unlink()
        subprocess.run(["git", "init", "-q", str(tree / "nested")], check=True, env=self.env)
        with self.assertRaises(RuntimeError):
            orchlib.fingerprint(tree)

    def test_fingerprint_command_prints_the_hash_for_the_current_checkout(self):
        tree = self.new_checkout("quartz-fp-cli")
        result = subprocess.run([str(CLI), "fingerprint"], cwd=tree, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, orchlib.fingerprint(tree) + "\n")
        outside = subprocess.run([str(CLI), "fingerprint"], cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(outside.returncode, 1)
        self.assertEqual(outside.stdout, "")

    def test_exclusion_in_main_checkout_and_linked_worktree_is_idempotent(self):
        exclude = self.repo / ".git" / "info" / "exclude"
        original = exclude.read_bytes() if exclude.exists() else b""
        linked = self.root / "linked.wt"
        self.git(self.repo, "worktree", "add", "-qb", "orch/linked", str(linked))
        for tree in (self.repo, linked, self.repo, linked):
            orchlib.ensure_excluded(tree)
        content = exclude.read_bytes()
        self.assertTrue(content.startswith(original))
        self.assertEqual(content[len(original):], b"/.orch/\n")
        self.assertEqual(content.split(b"\n").count(b"/.orch/"), 1)
        (linked / ".orch" / "x").mkdir(parents=True)
        (linked / ".orch" / "x" / "handoff.md").write_text("fictional\n")
        self.assertEqual(self.git(linked, "status", "--porcelain").stdout, "")

    def test_exclusion_creates_a_missing_file_and_fixes_an_unterminated_last_line(self):
        exclude = self.repo / ".git" / "info" / "exclude"
        shutil.rmtree(self.repo / ".git" / "info")
        orchlib.ensure_excluded(self.repo)
        self.assertEqual(exclude.read_bytes(), b"/.orch/\n")
        exclude.write_bytes(b"# keep\r\n*.tmp")
        orchlib.ensure_excluded(self.repo)
        self.assertEqual(exclude.read_bytes(), b"# keep\r\n*.tmp\n/.orch/\n")
        orchlib.ensure_excluded(self.repo)
        self.assertEqual(exclude.read_bytes(), b"# keep\r\n*.tmp\n/.orch/\n")


class ProofHookTests(Phase2Harness, Fixtures, unittest.TestCase):
    NAME = "quartz-builder"
    NO_PROOF = f"[orch] {NAME} stopped, no proof · pane w2:p1 · read: herdr agent read {NAME}"

    def setUp(self):
        super().setUp()
        self.patch_environment()
        self.tree = self.new_checkout("hook-tree")

    def proof_dir(self):
        path = self.tree / ".orch" / self.NAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    def make_row(self, role, *, proof=True):
        data = self.registry()
        row = data["agents"][f"{SESSION}/{self.NAME}"]
        row.update(role=role, tree=str(self.tree))
        if proof:
            row.update(proof=1, proof_id="fictional-id", test_cmd="true")
        self.registry_path.write_text(json.dumps(data))

    def good_handoff(self, **kwargs):
        write_build_proof(self.env, self.tree, self.NAME, **kwargs)

    def queue(self):
        return self.registry()["orchs"][ORCH]["queue"]

    def rising(self, status="done"):
        self.set_sequence_worker(status, state_seq=10, completion_seq=1)
        self.assertEqual(self.run_hook(self.status_event(status)).returncode, 0)
        return self.queue()

    def debounced(self, status="idle"):
        self.set_sequence_worker(status, state_seq=12)
        result = self.run_hook(self.status_event(status), extra_env={"ORCH_DEBOUNCE_SECONDS": "0.01"})
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.queue()

    def test_build_with_proof_notifies_done_through_both_paths(self):
        self.make_row("build")
        self.good_handoff()
        self.assertEqual(self.rising(), [phase2.notice(self.NAME, "done", "w2:p1")])
        self.write_registry()
        self.make_row("build")
        self.assertEqual(self.debounced(), [phase2.notice(self.NAME, "idle", "w2:p1")])

    def test_build_without_proof_gets_the_distinct_notice_through_both_paths(self):
        self.make_row("build")
        self.assertEqual(self.rising(), [self.NO_PROOF])
        self.write_registry()
        self.make_row("build")
        self.assertEqual(self.debounced(), [self.NO_PROOF])
        self.assertFalse(self.registry()["agents"][f"{SESSION}/{self.NAME}"]["turn_open"])

    def test_incomplete_oversized_symlinked_and_special_handoffs_count_as_missing(self):
        def missing_field(base):
            self.good_handoff(skip=("guards",))

        def empty_field(base):
            self.good_handoff(overrides={"run_sha256": ""})

        def oversized(base):
            self.good_handoff()
            handoff = base / "handoff.md"
            handoff.write_text(handoff.read_text() + "x" * (64 * 1024))

        def not_utf8(base):
            (base / "handoff.md").write_bytes(b"\xff\xfe" + b"run_log: x\n")

        def symlink(base):
            self.good_handoff()
            (base / "real.md").write_bytes((base / "handoff.md").read_bytes())
            (base / "handoff.md").unlink()
            os.symlink("real.md", base / "handoff.md")

        def directory(base):
            (base / "handoff.md").mkdir()

        def fifo(base):
            os.mkfifo(base / "handoff.md")

        def loaded_fifo(base):
            self.good_handoff()
            text = (base / "handoff.md").read_bytes()
            (base / "handoff.md").unlink()
            os.mkfifo(base / "handoff.md")
            held = os.open(base / "handoff.md", os.O_RDWR)
            self.addCleanup(os.close, held)
            os.write(held, text)

        for builder in (missing_field, empty_field, oversized, not_utf8, symlink, directory, fifo, loaded_fifo):
            with self.subTest(case=builder.__name__):
                self.write_registry()
                for leftover in (self.tree / ".orch").glob("*"):
                    subprocess.run(["rm", "-rf", str(leftover)], check=True)
                self.make_row("build")
                builder(self.proof_dir())
                self.assertEqual(self.rising(), [self.NO_PROOF])

    def test_review_needs_review_md_findings_and_an_executable_repro(self):
        cases = (
            ("complete", dict(), True),
            ("not-executable", dict(executable=False), False),
            ("no-repro", dict(skip_repro=True), False),
            ("no-review", dict(skip_review=True), False),
            ("empty-findings", dict(findings=""), False),
            ("malformed-findings", dict(findings="not-a-finding-list"), False),
            ("trailing-comma", dict(findings="F1,"), False),
            ("valid-list", dict(findings="F1, F2"), True),
        )
        for label, kwargs, expected in cases:
            with self.subTest(label=label):
                self.write_registry()
                subprocess.run(["rm", "-rf", str(self.tree / ".orch")], check=True)
                self.make_row("review")
                write_review_proof(self.tree, self.NAME, **kwargs)
                self.assertEqual(self.rising(), [phase2.notice(self.NAME, "done", "w2:p1")] if expected else [self.NO_PROOF])
        self.write_registry()
        subprocess.run(["rm", "-rf", str(self.tree / ".orch")], check=True)
        self.make_row("review")
        write_review_proof(self.tree, self.NAME, findings="none")
        self.assertEqual(self.debounced(), [phase2.notice(self.NAME, "idle", "w2:p1")])

    def test_false_blip_that_returns_to_working_still_yields_no_notice(self):
        self.make_row("build")
        self.set_sequence_worker("done", state_seq=50)
        env = self.env | {"HERDR_PLUGIN_EVENT": "pane.agent_status_changed",
                          "HERDR_PLUGIN_EVENT_JSON": json.dumps(self.status_event("done")["data"]), "ORCH_DEBOUNCE_SECONDS": "0.15"}
        process = subprocess.Popen([sys.executable, str(phase2.HOOK)], cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_for_worker_status("done")
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "working", "state_change_seq": 51}})
        self.assertEqual(self.run_hook(self.status_event("working")).returncode, 0)
        stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stderr or stdout)
        self.assertEqual(self.queue(), [])

    def test_explore_plan_and_legacy_rows_notify_done_without_proof(self):
        for label, role, proof in (("explore", "explore", True), ("plan", "plan", True), ("legacy", "build", False), ("no-role", None, True)):
            with self.subTest(label=label):
                self.write_registry()
                self.make_row(role or "x", proof=proof)
                if role is None:
                    data = self.registry()
                    data["agents"][f"{SESSION}/{self.NAME}"].pop("role")
                    self.registry_path.write_text(json.dumps(data))
                self.assertEqual(self.rising(), [phase2.notice(self.NAME, "done", "w2:p1")])

    def test_non_sequence_proof_rows_are_gated_on_the_legacy_path_too(self):
        data = self.registry()
        data["agents"][f"{SESSION}/{self.NAME}"]["status"] = "working"
        self.registry_path.write_text(json.dumps(data))
        for label, role, proof, good, expected in (
                ("no-proof", "build", True, False, self.NO_PROOF),
                ("with-proof", "build", True, True, phase2.notice(self.NAME, "done", "w2:p1")),
                ("legacy-row", "build", False, False, phase2.notice(self.NAME, "done", "w2:p1")),
                ("explore-row", "explore", True, False, phase2.notice(self.NAME, "done", "w2:p1"))):
            with self.subTest(label=label):
                self.write_registry()
                self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
                subprocess.run(["rm", "-rf", str(self.tree / ".orch")], check=True)
                self.make_row(role, proof=proof)
                if good:
                    self.good_handoff()
                self.assertEqual(self.run_hook(self.status_event("done")).returncode, 0)
                row = self.registry()["agents"][f"{SESSION}/{self.NAME}"]
                self.assertFalse(row.get("sequence_capable"))
                self.assertEqual(self.queue(), [expected])

    def test_blocked_notice_is_unchanged_for_proof_rows(self):
        self.make_row("build")
        self.set_sequence_worker("blocked", state_seq=10)
        self.assertEqual(self.run_hook(self.status_event("blocked")).returncode, 0)
        self.assertEqual(self.queue(), [phase2.notice(self.NAME, "blocked", "w2:p1")])

    def test_one_notice_per_turn_for_a_proof_row(self):
        self.make_row("build")
        self.set_sequence_worker("done", state_seq=10, completion_seq=1)
        for _ in range(2):
            self.assertEqual(self.run_hook(self.status_event("done")).returncode, 0)
        self.assertEqual(self.queue(), [self.NO_PROOF])

    def test_hook_proof_check_never_blocks_on_a_fifo_or_huge_file(self):
        self.make_row("build")
        os.mkfifo(self.proof_dir() / "handoff.md")
        self.set_sequence_worker("done", state_seq=10, completion_seq=1)
        result = subprocess.run([sys.executable, str(phase2.HOOK)], cwd=self.repo, text=True, capture_output=True, timeout=5,
                                env=self.env | {"HERDR_PLUGIN_EVENT": "pane.agent_status_changed",
                                                "HERDR_PLUGIN_EVENT_JSON": json.dumps(self.status_event("done")["data"])})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.queue(), [self.NO_PROOF])

    def test_registry_lock_stays_free_during_a_proof_row_debounce(self):
        self.make_row("build")
        self.set_sequence_worker("done", state_seq=50)
        env = self.env | {"HERDR_PLUGIN_EVENT": "pane.agent_status_changed",
                          "HERDR_PLUGIN_EVENT_JSON": json.dumps(self.status_event("done")["data"]), "ORCH_DEBOUNCE_SECONDS": "2"}
        process = subprocess.Popen([sys.executable, str(phase2.HOOK)], cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.wait_for_worker_status("done")
        started = time.monotonic()
        result = subprocess.run([str(CLI), "list"], cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=1.0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertIsNone(process.poll())
        process.communicate(timeout=5)


class ProofBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        env = mock.patch.dict(os.environ, {"HERDR_SESSION": "session-a"})
        env.start()
        self.addCleanup(env.stop)
        ttl = mock.patch.object(orchlib, "LIVE_FP_TTL", 0)
        ttl.start()
        self.addCleanup(ttl.stop)

    def agent(self, name, role, *, proof=True, files=True, status="working", **extra):
        tree = self.root / name
        tree.mkdir()
        row = {"project": "/fictional/orch-skill", "name": name, "pane": name, "orch": "session-a/p1", "status": status,
               "role": role, "tree": str(tree)}
        if proof:
            row.update(proof=1, proof_id=name, test_cmd="make test")
        base = tree / ".orch" / name
        if files and role == "build":
            base.mkdir(parents=True)
            write_build_proof(os.environ.copy(), self.make_repo(tree), name, guards="none", mutations=())
        elif files and role == "review":
            write_review_proof(tree, name)
        row.update(extra)
        return row

    def make_repo(self, tree):
        subprocess.run(["git", "init", "-q", str(tree)], check=True)
        subprocess.run(["git", "-C", str(tree), "-c", "user.name=Fictional Tester", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "seed"], check=True)
        orchlib.ensure_excluded(tree)
        return tree

    def bound(self, row, result, **binding):
        binding = orchlib.verdict_binding(row) | binding
        if row["role"] == "build":
            binding["fingerprint"] = orchlib.fingerprint(row["tree"])
        row["verdict"] = {"result": result, "time": 1, "binding": binding}

    def registry(self):
        rows = {
            "a-empty": self.agent("a-empty", "build", files=False),
            "b-present": self.agent("b-present", "build"),
            "c-passing": self.agent("c-passing", "build"),
            "d-failing": self.agent("d-failing", "build"),
            "e-stale": self.agent("e-stale", "build"),
            "f-review": self.agent("f-review", "review"),
            "g-explore": self.agent("g-explore", "explore", proof=False, files=False),
            "h-legacy": self.agent("h-legacy", "build", proof=False, files=False),
            "i-plan": self.agent("i-plan", "plan", proof=False, files=False),
        }
        self.bound(rows["c-passing"], "passing")
        self.bound(rows["d-failing"], "failing")
        self.bound(rows["e-stale"], "passing")
        handoff = pathlib.Path(rows["e-stale"]["tree"]) / ".orch" / "e-stale" / "handoff.md"
        handoff.write_text(handoff.read_text() + "late_note: edited after the verdict\n")
        self.bound(rows["f-review"], "passing", against="/fictional/checkout", want="REPRODUCED")
        return {"version": 1,
                "orchs": {"session-a/p1": {"project": "/fictional/orch-skill", "name": "orch-main", "pane": "p1", "status": "idle", "queue": []}},
                "agents": {f"session-a/{name}": row for name, row in rows.items()}}

    def render(self, width, data, enabled=False):
        titles = {key: f"Fictional task {key.split('/')[1]}" for key in data["agents"]}
        return board.render(data, width, enabled, "registry.json", "2026-10-19 12:34:56", now=1000, pane_titles=titles)

    def test_proof_states_and_blank_rows(self):
        data = self.registry()
        states = {name: orchlib.proof_state(data["agents"][f"session-a/{name}"]) for name in
                  ("a-empty", "b-present", "c-passing", "d-failing", "e-stale", "f-review", "g-explore", "h-legacy", "i-plan")}
        self.assertEqual(states, {"a-empty": "missing", "b-present": "present", "c-passing": "passing", "d-failing": "failing",
                                  "e-stale": "present", "f-review": "passing", "g-explore": "", "h-legacy": "", "i-plan": ""})

    def test_verdict_stops_binding_when_the_run_log_or_test_command_changes(self):
        row = self.registry()["agents"]["session-a/c-passing"]
        self.assertEqual(orchlib.proof_state(row), "passing")
        row["test_cmd"] = "make other"
        self.assertEqual(orchlib.proof_state(row), "present")
        row["test_cmd"] = "make test"
        self.assertEqual(orchlib.proof_state(row), "passing")
        log = pathlib.Path(row["tree"]) / ".orch" / "c-passing" / "run-1.log"
        log.write_text(log.read_text() + "late line\n")
        self.assertEqual(orchlib.proof_state(row), "present")

    def test_live_fingerprint_is_cached_and_bounded(self):
        tree = self.make_repo(self.root / "bounded")
        with mock.patch.object(orchlib, "LIVE_FP_TTL", 60), mock.patch.object(orchlib, "LIVE_FP_CACHE", {}), \
                mock.patch.object(orchlib, "fingerprint", return_value="a" * 64) as probe:
            self.assertEqual(orchlib.live_fingerprint(tree), "a" * 64)
            self.assertEqual(orchlib.live_fingerprint(tree), "a" * 64)
        probe.assert_called_once_with(tree, timeout=orchlib.LIVE_FP_TIMEOUT)
        with mock.patch.object(orchlib, "LIVE_FP_CACHE", {}), mock.patch.object(orchlib, "fingerprint", side_effect=RuntimeError("fingerprint timed out")):
            self.assertIsNone(orchlib.live_fingerprint(tree))

    def test_fingerprint_timeout_stops_a_slow_git(self):
        tree = self.make_repo(self.root / "slow-git")
        shim = self.root / "shim"
        shim.mkdir()
        (shim / "git").write_text("#!/bin/sh\nsleep 5\n")
        (shim / "git").chmod(0o755)
        started = time.monotonic()
        with mock.patch.dict(os.environ, {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                orchlib.fingerprint(tree, timeout=0.3)
        self.assertLess(time.monotonic() - started, 2.0)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            orchlib.fingerprint(tree, timeout=0)

    def test_board_shows_present_when_the_live_fingerprint_is_unknown(self):
        row = self.registry()["agents"]["session-a/c-passing"]
        with mock.patch.object(orchlib, "LIVE_FP_CACHE", {}), mock.patch.object(orchlib, "fingerprint", side_effect=RuntimeError("fingerprint timed out")):
            self.assertEqual(orchlib.proof_state(row), "present")
            row["verdict"]["binding"]["fingerprint"] = None
            self.assertEqual(orchlib.proof_state(row), "present")

    def test_fingerprint_deadline_is_checked_between_untracked_files(self):
        tree = self.make_repo(self.root / "many-files")
        (tree / "one.txt").write_text("one\n")
        clock = [0.0]
        real = orchlib.git_output

        def slow_listing(path, *args, timeout=None):
            out = real(path, *args, timeout=timeout)
            if args[0] == "ls-files":
                clock[0] = 100.0
            return out

        with mock.patch.object(orchlib.time, "monotonic", side_effect=lambda: clock[0]), mock.patch.object(orchlib, "git_output", slow_listing):
            with self.assertRaisesRegex(RuntimeError, "fingerprint timed out"):
                orchlib.fingerprint(tree, timeout=5)

    def test_review_verdict_without_against_binding_is_only_present(self):
        data = self.registry()
        row = data["agents"]["session-a/f-review"]
        row["verdict"]["binding"].pop("against")
        self.assertEqual(orchlib.proof_state(row), "present")

    def test_closed_proof_row_keeps_its_verdict_and_unverified_closed_row_is_blank(self):
        data = self.registry()
        passing = data["agents"]["session-a/c-passing"]
        passing.update(state="closed", status="closed")
        self.assertEqual(orchlib.proof_state(passing), "passing")
        missing = data["agents"]["session-a/a-empty"]
        missing.update(state="closed", status="closed")
        self.assertEqual(orchlib.proof_state(missing), "")

    def test_exact_frames_at_four_widths(self):
        data = self.registry()
        for width in (55, 67, 100, 160):
            with self.subTest(width=width):
                actual = "\n".join(line.rstrip() for line in self.render(width, data).splitlines())
                expected = (FIXTURES / f"board-proof-{width}.txt").read_text().rstrip("\n")
                self.assertEqual(actual, expected)
                self.assertTrue(all(board.display_width(line) == width for line in self.render(width, data).splitlines() if line))

    def test_proof_state_refreshes_without_a_registry_change(self):
        data = self.registry()
        text = self.render(100, data)
        self.assertIn("missing", text)
        base = pathlib.Path(data["agents"]["session-a/a-empty"]["tree"]) / ".orch" / "a-empty"
        base.mkdir(parents=True)
        write_build_proof(os.environ.copy(), self.make_repo(base.parent.parent), "a-empty", guards="none", mutations=())
        self.assertNotIn("missing", self.render(100, data))

    def test_proof_cell_colors(self):
        data = self.registry()
        with mock.patch("plugin.board.terminal_color_mode", return_value="16"):
            text = self.render(160, data, enabled=True)
        for state, code in (("missing", "33"), ("present", "2;37"), ("failing", "1;31"), ("passing", "32")):
            self.assertIn(f"\033[{code}m{state}\033[0m", text)


class ProofCliTests(unittest.TestCase):
    setUp = phase1.PhaseOne.setUp
    tearDown = phase1.PhaseOne.tearDown
    runcli = phase1.PhaseOne.runcli
    calls = phase1.PhaseOne.calls
    state = phase1.PhaseOne.state
    save_state = phase1.PhaseOne.save_state
    reg = phase1.PhaseOne.reg
    spawn = phase1.PhaseOne.spawn

    def git(self, tree, *args):
        return run_git(self.env, tree, *args)

    def spawn_proof(self, name, where="worktree", test_cmd="test -f work.txt"):
        self.spawn(name, where, extra=("--test-cmd", test_cmd))
        row = self.state()["agents"][f"session-a/{name}"]
        return row, orchlib.proof_dir(row)

    def test_build_spawn_requires_test_cmd(self):
        self.reg()
        brief = self.root / "brief.txt"
        result = self.runcli("spawn", "needs-cmd", "--role", "build", "--kind", "claude", "--where", "worktree", "--brief", str(brief), ok=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "orch spawn: --test-cmd is required with --role build\n")
        blank = self.runcli("spawn", "blank-cmd", "--role", "build", "--test-cmd", "  ", "--kind", "claude", "--where", "worktree", "--brief", str(brief), ok=False)
        self.assertEqual(blank.returncode, 2)
        self.assertNotIn("session-a/needs-cmd", self.state()["agents"])
        self.assertFalse(any(call[:2] in (["worktree", "create"], ["agent", "start"]) for call in self.calls()))

    def test_proof_spawn_marks_the_row_and_appends_the_rules_to_the_brief(self):
        self.reg()
        row, base = self.spawn_proof("proofy", test_cmd="python3 -m unittest")
        self.assertEqual(row["proof"], 1)
        self.assertRegex(row["proof_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(row["test_cmd"], "python3 -m unittest")
        self.assertEqual(base, pathlib.Path(row["worktree"]) / ".orch" / "proofy")
        self.assertTrue(base.is_dir())
        brief = (self.root / "brief.txt").read_text()
        self.assertEqual(brief.count(orchlib.PROOF_MARK), 1)
        self.assertTrue(brief.startswith("Build fictional widget\n\n" + orchlib.PROOF_MARK + "\n"))
        self.assertIn("Test command (the one the orch will run clean): `python3 -m unittest`", brief)
        self.assertIn(f"{{ python3 -m unittest ; }} > {base}/run-<n>.log 2>&1", brief)
        self.assertIn(f"\n    {base}\n", brief)
        self.assertNotIn("{test_cmd}", brief)
        self.assertNotIn("{proof_dir}", brief)
        self.assertNotIn("### Reviewer", brief)
        prompts = [call for call in self.calls() if call[:2] == ["agent", "prompt"]]
        self.assertEqual(prompts, [["agent", "prompt", "proofy", f"The user asked for this: {(self.root / 'brief.txt').resolve()}"]])
        self.assertNotIn("\n", prompts[0][3])

    def test_second_spawn_with_the_same_brief_replaces_the_rules(self):
        self.reg()
        self.spawn_proof("first-rules")
        brief = self.root / "brief.txt"
        self.runcli("spawn", "second-rules", "--role", "review", "--kind", "claude", "--where", "pane", "--brief", str(brief))
        text = brief.read_text()
        self.assertEqual(text.count(orchlib.PROOF_MARK), 1)
        self.assertEqual(text.count("Build fictional widget"), 1)
        self.assertIn("### Reviewer", text)
        self.assertNotIn("### Builder", text)

    def test_review_spawn_uses_the_review_rules_and_the_orch_tree(self):
        self.reg()
        brief = self.root / "brief.txt"
        self.runcli("spawn", "reviewer", "--role", "review", "--kind", "claude", "--where", "pane", "--brief", str(brief))
        row = self.state()["agents"]["session-a/reviewer"]
        self.assertEqual((row["proof"], row["test_cmd"]), (1, None))
        base = self.repo / ".orch" / "reviewer"
        self.assertTrue(base.is_dir())
        text = brief.read_text()
        self.assertIn("### Reviewer", text)
        self.assertNotIn("### Builder", text)
        self.assertIn(f"{base}/review.md", text)
        self.assertEqual(text.count(orchlib.PROOF_MARK), 1)

    def test_other_roles_and_bad_names_get_no_proof(self):
        self.reg()
        brief = self.root / "brief.txt"
        for role in ("plan", "explore"):
            self.runcli("spawn", f"{role}-worker", "--role", role, "--kind", "claude", "--where", "pane", "--brief", str(brief))
            self.assertNotIn("proof", self.state()["agents"][f"session-a/{role}-worker"])
        self.assertEqual(brief.read_text(), "Build fictional widget")
        bad = self.runcli("spawn", "bad/name", "--role", "review", "--kind", "claude", "--where", "pane", "--brief", str(brief), ok=False)
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(bad.stderr, "orch spawn: a review worker name must match [A-Za-z0-9][A-Za-z0-9._-]*: bad/name\n")
        self.assertNotIn("session-a/bad/name", self.state()["agents"])

    def test_repeated_spawn_keeps_one_exclude_line(self):
        self.reg()
        self.spawn_proof("first-proof")
        self.spawn_proof("second-proof")
        exclude = (self.repo / ".git" / "info" / "exclude").read_bytes()
        self.assertEqual(exclude.split(b"\n").count(b"/.orch/"), 1)
        wt = pathlib.Path(self.state()["agents"]["session-a/first-proof"]["worktree"])
        (wt / ".orch" / "first-proof" / "note.txt").write_text("fictional\n")
        self.assertEqual(self.git(wt, "status", "--porcelain").stdout, "")

    def test_list_idle_never_offers_proof_rows(self):
        self.reg()
        self.spawn_proof("idle-proof")
        self.spawn("idle-plain", "pane", extra=("--test-cmd", "true"))
        data = self.state()
        for name in ("idle-proof", "idle-plain"):
            data["agents"][f"session-a/{name}"]["status"] = "idle"
        data["agents"]["session-a/idle-plain"].pop("proof")
        self.save_state(data)
        self.assertEqual(self.runcli("list", "--idle").stdout, "build\tidle-plain\tidle\tpane\n")
        self.assertEqual(self.runcli("list").stdout, "build\tidle-plain\tidle\tpane\nbuild\tidle-proof\tidle\tworktree\n")

    def test_verify_merge_and_close_a_proof_worker_without_discard(self):
        self.reg()
        row, base = self.spawn_proof("closer")
        wt = pathlib.Path(row["worktree"])
        (wt / "work.txt").write_text("fictional work\n")
        self.git(wt, "add", "work.txt")
        self.git(wt, "commit", "-qm", "fictional work")
        write_build_proof(self.env, wt, "closer", guards="none", mutations=())
        result = self.runcli("verify", "closer")
        self.assertEqual(result.stdout.splitlines()[-1], "RESULT: PASS")
        self.git(self.repo, "merge", "--ff-only", "orch/closer")
        before = {path.relative_to(base).as_posix(): path.read_bytes() for path in sorted(base.rglob("*")) if path.is_file()}
        self.assertIn("verify-clean-1.log", before)
        self.runcli("close", "closer")
        agent = self.state()["agents"]["session-a/closer"]
        self.assertEqual(agent["state"], "closed")
        archive = self.home / "orch" / "proof" / "session-a" / "closer"
        self.assertEqual({path.relative_to(archive).as_posix(): path.read_bytes() for path in sorted(archive.rglob("*")) if path.is_file()}, before)
        self.assertEqual(agent["proof_archive"], str(archive))
        self.assertFalse(wt.exists())

    def test_close_refuses_an_unrelated_ignored_file_but_not_the_proof_dir(self):
        self.reg()
        row, base = self.spawn_proof("picky")
        wt = pathlib.Path(row["worktree"])
        (base / "handoff.md").write_text("fictional\n")
        with open(self.repo / ".git" / "info" / "exclude", "a") as stream:
            stream.write("/scratch.txt\n")
        (wt / "scratch.txt").write_text("ignored but not owned\n")
        result = self.runcli("close", "picky", ok=False)
        self.assertIn("dirty paths: !! scratch.txt", result.stderr)
        self.assertTrue(wt.exists())
        self.assertNotEqual(self.state()["agents"]["session-a/picky"]["state"], "closed")
        (wt / "scratch.txt").unlink()
        self.runcli("close", "picky")
        self.assertEqual(self.state()["agents"]["session-a/picky"]["state"], "closed")

    def test_symlinked_orch_dir_is_refused_by_spawn_and_close(self):
        self.reg()
        external = self.root / "unrelated-directory"
        keep = external / "symlinked" / "keep.txt"
        keep.parent.mkdir(parents=True)
        keep.write_text("unrelated bytes\n")
        (self.repo / ".orch").symlink_to(external, target_is_directory=True)
        brief = self.root / "brief.txt"
        result = self.runcli("spawn", "symlinked", "--role", "review", "--kind", "claude", "--where", "pane", "--brief", str(brief), ok=False)
        self.assertIn("proof dir refused;", result.stderr)
        self.assertEqual(keep.read_text(), "unrelated bytes\n")
        self.assertEqual(brief.read_text(), "Build fictional widget")

    def test_close_never_deletes_through_a_symlinked_proof_dir(self):
        self.reg()
        row, base = self.spawn_proof("swapped")
        wt = pathlib.Path(row["worktree"])
        external = self.root / "unrelated-target"
        external.mkdir()
        (external / "keep.txt").write_text("unrelated bytes\n")
        subprocess.run(["rm", "-rf", str(base)], check=True)
        base.symlink_to(external, target_is_directory=True)
        result = self.runcli("close", "swapped", ok=False)
        self.assertIn("proof dir refused;", result.stderr)
        self.assertEqual((external / "keep.txt").read_text(), "unrelated bytes\n")
        self.assertTrue(wt.exists())
        self.assertNotEqual(self.state()["agents"]["session-a/swapped"]["state"], "closed")

    def test_close_retry_archives_the_latest_proof(self):
        self.reg()
        row, base = self.spawn_proof("retrier")
        wt = pathlib.Path(row["worktree"])
        (base / "handoff.md").write_text("round one\n")
        (wt / "blocker.txt").write_text("dirty\n")
        self.runcli("close", "retrier", ok=False)
        archive = self.home / "orch" / "proof" / "session-a" / "retrier"
        self.assertEqual((archive / "handoff.md").read_text(), "round one\n")
        (base / "handoff.md").write_text("round two\n")
        (wt / "blocker.txt").unlink()
        self.runcli("close", "retrier")
        self.assertEqual((archive / "handoff.md").read_text(), "round two\n")
        self.assertEqual([path.name for path in archive.parent.iterdir()], ["retrier"])
        self.assertFalse(wt.exists())

    def test_close_accepts_owned_proof_files_with_non_ascii_names(self):
        self.reg()
        row, base = self.spawn_proof("accented")
        (base / "m\u00e9mo \"q\".txt").write_text("proof attachment\n")
        self.runcli("close", "accented")
        archive = self.home / "orch" / "proof" / "session-a" / "accented"
        self.assertEqual((archive / "m\u00e9mo \"q\".txt").read_text(), "proof attachment\n")
        self.assertEqual(self.state()["agents"]["session-a/accented"]["state"], "closed")

    def test_install_and_check_require_the_proof_rules(self):
        self.reg()
        source = self.root / "fictional-source"
        shutil.copytree(ROOT / "skills", source / "skills")
        installed = self.root / "installed-plugin" / "orch"
        shutil.copytree(ROOT / "plugin", installed, ignore=shutil.ignore_patterns("__pycache__"))
        argv = ["bash", str(ROOT / "scripts" / "install-skill.sh")]
        options = ["--source", str(source), "--plugin-dir", str(installed), "--home", str(self.userhome)]
        complete = subprocess.run(argv + ["install"] + options, env=self.env, text=True, capture_output=True)
        self.assertEqual(complete.returncode, 0, complete.stderr)
        self.assertEqual(subprocess.run(argv + ["check"] + options, env=self.env, text=True, capture_output=True).returncode, 0)
        (source / "skills" / "orch" / "references" / "proof.md").unlink()
        for mode in ("install", "check"):
            with self.subTest(mode=mode):
                result = subprocess.run(argv + [mode] + options, env=self.env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr.splitlines()[0], "incomplete orch skill source: missing skills/orch/references/proof.md")

    def test_close_fails_without_removing_anything_when_the_archive_cannot_be_written(self):
        self.reg()
        row, base = self.spawn_proof("stuck")
        wt = pathlib.Path(row["worktree"])
        (base / "handoff.md").write_text("fictional\n")
        (self.home / "orch" / "proof").write_text("a file where the archive directory should be\n")
        result = self.runcli("close", "stuck", ok=False)
        self.assertIn("close refused; cannot archive proof", result.stderr)
        self.assertTrue(wt.exists())
        self.assertTrue((base / "handoff.md").exists())
        self.assertNotEqual(self.state()["agents"]["session-a/stuck"]["state"], "closed")
        self.assertFalse(any(call[:2] in (["worktree", "remove"], ["pane", "close"]) for call in self.calls()))

    def test_split_pane_reviewer_close_archives_then_removes_its_proof_dir(self):
        self.reg()
        brief = self.root / "brief.txt"
        self.runcli("spawn", "pane-review", "--role", "review", "--kind", "claude", "--where", "pane", "--brief", str(brief))
        base = self.repo / ".orch" / "pane-review"
        write_review_proof(self.repo, "pane-review")
        before = {path.name: path.read_bytes() for path in base.iterdir()}
        self.runcli("close", "pane-review")
        archive = self.home / "orch" / "proof" / "session-a" / "pane-review"
        self.assertEqual({path.name: path.read_bytes() for path in archive.iterdir()}, before)
        self.assertFalse(base.exists())
        self.assertEqual(self.state()["agents"]["session-a/pane-review"]["state"], "closed")


class ProofSpacedPathTests(unittest.TestCase):
    """The generated final-run command must survive a checkout path with a space and a quote."""
    tearDown = phase1.PhaseOne.tearDown
    runcli = phase1.PhaseOne.runcli
    calls = phase1.PhaseOne.calls
    state = phase1.PhaseOne.state
    reg = phase1.PhaseOne.reg
    spawn = phase1.PhaseOne.spawn

    def setUp(self):
        parent = tempfile.mkdtemp(prefix="it's a space ")
        self.addCleanup(shutil.rmtree, parent, True)
        patcher = mock.patch.object(tempfile, "tempdir", parent)
        patcher.start()
        try:
            phase1.PhaseOne.setUp(self)
        finally:
            patcher.stop()

    def test_generated_run_command_works_in_a_path_with_a_space_and_a_quote(self):
        self.reg()
        self.spawn("spaced", "worktree", extra=("--test-cmd", "true"))
        row = self.state()["agents"]["session-a/spaced"]
        base = orchlib.proof_dir(row)
        self.assertIn(" ", str(base))
        self.assertIn("'", str(base))
        text = (self.root / "brief.txt").read_text()
        lines = [line.strip() for line in text.splitlines() if "run-<n>.log 2>&1" in line]
        self.assertEqual(lines, [f"{{ true ; }} > {shlex.quote(str(base))}/run-<n>.log 2>&1; echo \"exit=$?\" >> {shlex.quote(str(base))}/run-<n>.log"])
        result = subprocess.run(["/bin/sh", "-c", lines[0].replace("<n>", "1")], cwd=row["tree"], env=self.env, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual((base / "run-1.log").read_text(), "exit=0\n")


if __name__ == "__main__":
    unittest.main()
