import json
import os
import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugin" / "hook.py"
CLI = ROOT / "plugin" / "orch"
FIXTURES = ROOT / "tests" / "fixtures" / "herdr"
SESSION = "orch-phase2-test"
ORCH = f"{SESSION}/w2:p9"
OTHER_ORCH = f"{SESSION}/w2:p8"


def load_events():
    return [json.loads(line) for line in (FIXTURES / "socket-events.jsonl").read_text().splitlines()]


def event_for(agent, status):
    return next(
        item for item in load_events()
        if item["event"] == "pane.agent_status_changed"
        and item["data"].get("agent") == agent
        and item["data"].get("agent_status") == status
    )


def notice(name, status, pane):
    return f"[orch] {name} {status} · pane {pane} · read: herdr agent read {name}"


class PhaseTwo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.state_home = self.root / "state"
        self.state_home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.jsonl"
        self.herdr_state = self.root / "herdr.json"
        self.registry_path = self.state_home / "orch" / "registry.json"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Fictional Tester"], check=True)
        (self.repo / "seed.txt").write_text("seed\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "seed.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture seed"], check=True)

        fake = self.bin / "herdr"
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
state = json.load(open(os.environ["HERDR_TEST_STATE"]))
if args[:2] == ["agent", "get"]:
    if os.environ.get("HERDR_DELAY_GET"):
        time.sleep(float(os.environ["HERDR_DELAY_GET"]))
    if os.environ.get("HERDR_AGENT_GET_FAILURE") == "1":
        print("fixture server unavailable", file=sys.stderr)
        sys.exit(2)
    agent = state["panes"].get(args[2])
    if agent is None:
        print(json.dumps({"error": {"code": "agent_not_found"}}), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"result": {"agent": agent}}))
elif args[:2] == ["agent", "prompt"]:
    if os.environ.get("FAIL_PROMPT") == "1":
        print("simulated prompt failure", file=sys.stderr)
        sys.exit(2)
    with open(os.environ["PROMPTS"], "a") as stream:
        stream.write(json.dumps(args[2:]) + "\\n")
    print(json.dumps({"result": {"type": "agent_prompted"}}))
elif args[:2] == ["pane", "list"]:
    print(json.dumps({"result": {"panes": [{"pane_id": "w2:p8"}, {"pane_id": "w2:p9"}]}}))
elif args[:3] == ["plugin", "pane", "open"]:
    print(json.dumps({"result": {"pane": {"pane_id": "w2:board"}}}))
else:
    print(json.dumps({"result": {}}))
''')
        fake.chmod(0o755)
        clean = os.environ.copy()
        for key in ("FAIL_PROMPT", "CALLS", "PROMPTS", "HERDR_TEST_STATE"):
            clean.pop(key, None)
        self.env = clean | {
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.state_home),
            "PATH": str(self.bin) + os.pathsep + clean["PATH"],
            "CALLS": str(self.calls),
            "PROMPTS": str(self.root / "prompts.jsonl"),
            "HERDR_TEST_STATE": str(self.herdr_state),
            "HERDR_ENV": "1",
            "HERDR_SESSION": SESSION,
            "HERDR_PANE_ID": "w2:p9",
            "HERDR_WORKSPACE_ID": "w2",
            "HERDR_TAB_ID": "w2:t1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.write_registry()
        self.write_herdr_state()

    def tearDown(self):
        self.tmp.cleanup()

    def registry(self):
        return json.loads(self.registry_path.read_text())

    def write_registry(self, *, queue=None, orch_status="working", worker_status="working"):
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "orchs": {
                ORCH: {"project": str(self.repo), "name": "orch-main", "kind": "claude", "workspace": "w2", "tab": "w2:t1", "pane": "w2:p9", "status": orch_status, "gone": False, "queue": list(queue or [])},
                OTHER_ORCH: {"project": str(self.repo), "name": "orch-other", "kind": "codex", "workspace": "w2", "tab": "w2:t1", "pane": "w2:p8", "status": "working", "gone": False, "queue": []},
            },
            "agents": {
                f"{SESSION}/quartz-builder": {"name": "quartz-builder", "pane": "w2:p1", "orch": ORCH, "project": str(self.repo), "kind": "claude", "state": "live", "status": worker_status, "created": ["pane:w2:p1"]},
                f"{SESSION}/maple-worker": {"name": "maple-worker", "pane": "w2:p2", "orch": OTHER_ORCH, "project": str(self.repo), "kind": "codex", "state": "live", "status": "working", "created": ["pane:w2:p2"]},
                f"{SESSION}/sample-worker": {"name": "sample-worker", "pane": "w2:p3", "orch": ORCH, "project": str(self.repo), "kind": "custom", "state": "live", "status": "unknown", "created": ["pane:w2:p3"]},
            },
        }
        self.registry_path.write_text(json.dumps(data))

    def write_herdr_state(self, **updates):
        panes = {
            "w2:p1": {"agent": "claude", "agent_status": "working"},
            "w2:p2": {"agent": "codex", "agent_status": "working"},
            "w2:p3": {"agent": "sample-worker", "agent_status": "unknown"},
            "w2:p8": {"agent": "codex", "agent_status": "working"},
            "w2:p9": {"agent": "claude", "agent_status": "working"},
        }
        panes.update(updates)
        self.herdr_state.write_text(json.dumps({"panes": panes}))

    def run_hook(self, item, *, fail_prompt=False):
        env = self.env | {
            "HERDR_PLUGIN_EVENT": item["event"].replace("pane_closed", "pane.closed"),
            "HERDR_PLUGIN_EVENT_JSON": json.dumps(item["data"]),
        }
        if fail_prompt:
            env["FAIL_PROMPT"] = "1"
        return subprocess.run([sys.executable, str(HOOK)], cwd=self.repo, env=env, text=True, capture_output=True)

    def run_cli(self, *args, env=None, ok=True):
        result = subprocess.run([str(CLI), *args], cwd=self.repo, env=env or self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def prompt_calls(self):
        if not (self.root / "prompts.jsonl").exists():
            return []
        return [json.loads(line) for line in (self.root / "prompts.jsonl").read_text().splitlines()]

    def test_fixture_events_cover_provider_and_custom_statuses(self):
        records = load_events()
        statuses = {(r["data"].get("agent"), r["data"].get("agent_status")) for r in records if r["event"] == "pane.agent_status_changed"}
        self.assertTrue({("claude", "working"), ("claude", "done"), ("codex", "working"), ("sample-worker", "blocked"), ("sample-worker", "unknown")} <= statuses)
        self.assertEqual({r["data"]["pane_id"] for r in records if r["event"] == "pane_closed"}, {"w2:p1", "w2:p2", "w2:p3"})
        for kind in ("claude", "codex"):
            item = json.loads((FIXTURES / f"agent-get-{kind}.json").read_text())
            self.assertEqual(item["result"]["type"], "agent_info")
            self.assertEqual(item["result"]["agent"]["agent"], kind)
            self.assertEqual(item["result"]["agent"]["agent_status"], "idle")

    def test_notice_is_queued_for_the_owning_orch_only(self):
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
        result = self.run_hook(event_for("claude", "done"))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.registry()
        self.assertEqual(data["orchs"][ORCH]["queue"], [notice("quartz-builder", "done", "w2:p1")])
        self.assertEqual(data["orchs"][OTHER_ORCH]["queue"], [])

    def test_repeated_status_queues_one_notice(self):
        self.write_herdr_state(**{"w2:p3": {"agent": "sample-worker", "agent_status": "blocked"}})
        data = self.registry()
        data["agents"][f"{SESSION}/sample-worker"]["status"] = "unknown"
        self.registry_path.write_text(json.dumps(data))
        item = event_for("sample-worker", "blocked")
        for _ in range(2):
            result = self.run_hook(item)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [notice("sample-worker", "blocked", "w2:p3")])

    def test_done_idle_flip_queues_no_notice(self):
        self.write_registry(worker_status="done")
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "idle"}})
        result = self.run_hook(event_for("claude", "idle"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [])
        self.assertEqual(self.registry()["agents"][f"{SESSION}/quartz-builder"]["status"], "idle")
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
        result = self.run_hook(event_for("claude", "done"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [])
        self.assertEqual(self.registry()["agents"][f"{SESSION}/quartz-builder"]["status"], "done")

    def test_idle_and_unknown_to_blocked_queue_notice(self):
        item = event_for("sample-worker", "blocked")
        self.write_herdr_state(**{"w2:p3": {"agent": "sample-worker", "agent_status": "blocked"}})
        for old in ("idle", "unknown"):
            with self.subTest(old=old):
                self.write_registry(worker_status=old)
                data = self.registry()
                data["agents"][f"{SESSION}/sample-worker"]["status"] = old
                self.registry_path.write_text(json.dumps(data))
                result = self.run_hook(item)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [notice("sample-worker", "blocked", "w2:p3")])

    def test_out_of_order_event_uses_live_status(self):
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
        result = self.run_hook(event_for("claude", "working"))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.registry()
        self.assertEqual(data["agents"][f"{SESSION}/quartz-builder"]["status"], "done")
        self.assertEqual(data["orchs"][ORCH]["queue"], [notice("quartz-builder", "done", "w2:p1")])

    def test_queue_is_held_while_orch_is_working_or_blocked(self):
        item = event_for("claude", "done")
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
        for status in ("working", "blocked"):
            with self.subTest(status=status):
                self.write_registry(orch_status=status)
                self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}, "w2:p9": {"agent": "claude", "agent_status": status}})
                result = self.run_hook(item)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [notice("quartz-builder", "done", "w2:p1")])
                self.assertEqual(self.prompt_calls(), [])

    def test_queue_flushes_as_one_prompt_when_orch_goes_idle(self):
        queued = ["first fictional notice", "second fictional notice"]
        self.write_registry(queue=queued)
        self.write_herdr_state(**{"w2:p9": {"agent": "claude", "agent_status": "idle"}})
        item = {"event": "pane.agent_status_changed", "data": {"pane_id": "w2:p9", "agent_status": "idle"}}
        result = self.run_hook(item)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.registry()["orchs"][ORCH]
        self.assertEqual(self.prompt_calls(), [["w2:p9", "first fictional notice\nsecond fictional notice"]])
        self.assertEqual(data["queue"], [])
        self.assertEqual(data["status"], "working")

    def test_failed_prompt_keeps_queue_and_next_cli_command_delivers(self):
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}, "w2:p9": {"agent": "claude", "agent_status": "idle"}})
        result = self.run_hook(event_for("claude", "done"), fail_prompt=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = [notice("quartz-builder", "done", "w2:p1")]
        self.assertEqual(self.registry()["orchs"][ORCH]["queue"], expected)
        self.run_cli("list", env=self.env | {"HERDR_PANE_ID": "w2:p9"})
        self.assertEqual(self.registry()["orchs"][ORCH]["queue"], [])
        self.assertEqual(self.prompt_calls(), [["w2:p9", expected[0]]])

    def test_orch_close_keeps_queue_and_adoption_delivers(self):
        queued = ["old fictional notice"]
        self.write_registry(queue=queued, worker_status="done")
        data = self.registry()
        data["agents"].pop(f"{SESSION}/sample-worker")
        self.registry_path.write_text(json.dumps(data))
        close = {"event": "pane.closed", "data": {"pane_id": "w2:p9", "type": "pane_closed", "workspace_id": "w2"}}
        result = self.run_hook(close)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.registry()
        self.assertTrue(data["orchs"][ORCH]["gone"])
        self.assertEqual(data["orchs"][ORCH]["queue"], queued)
        adopter = f"{SESSION}/w2:p7"
        self.write_herdr_state(**{"w2:p7": {"agent": "claude", "agent_status": "idle"}})
        self.run_cli("register", "--name", "orch-adopter", env=self.env | {"HERDR_PANE_ID": "w2:p7"})
        data = self.registry()
        self.assertEqual(data["orchs"][ORCH]["queue"], [], self.calls.read_text() if self.calls.exists() else "no Herdr calls recorded")
        self.assertEqual(data["agents"][f"{SESSION}/quartz-builder"]["orch"], adopter)
        self.assertEqual(self.prompt_calls(), [["w2:p7", "old fictional notice\n[orch] quartz-builder done · pane w2:p1 · read: herdr agent read quartz-builder"]])

    def test_events_after_close_are_ignored(self):
        close = {"event": "pane.closed", "data": {"pane_id": "w2:p1", "type": "pane_closed", "workspace_id": "w2"}}
        self.write_herdr_state(**{"w2:p1": {"agent": "claude", "agent_status": "done"}})
        first = self.run_hook(close)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_hook(event_for("claude", "done"))
        self.assertEqual(second.returncode, 0, second.stderr)
        data = self.registry()
        agent = data["agents"][f"{SESSION}/quartz-builder"]
        self.assertEqual(agent["state"], "closed")
        self.assertEqual(data["orchs"][ORCH]["queue"], [notice("quartz-builder", "closed", "w2:p1")])

    def test_missing_live_agent_is_treated_as_closed(self):
        self.write_herdr_state(**{"w2:p1": None})
        result = self.run_hook(event_for("claude", "working"))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.registry()
        agent = data["agents"][f"{SESSION}/quartz-builder"]
        self.assertEqual(agent["state"], "closed")
        self.assertEqual(agent["status"], "closed")
        self.assertEqual(data["orchs"][ORCH]["queue"], [notice("quartz-builder", "closed", "w2:p1")])

    def test_herdr_lookup_error_does_not_mark_agent_closed(self):
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            cwd=self.repo,
            env=self.env | {
                "HERDR_PLUGIN_EVENT": "pane.agent_status_changed",
                "HERDR_PLUGIN_EVENT_JSON": json.dumps(event_for("claude", "working")["data"]),
                "HERDR_AGENT_GET_FAILURE": "1",
            },
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), "orch hook: RuntimeError: herdr agent get failed: fixture server unavailable")
        agent = self.registry()["agents"][f"{SESSION}/quartz-builder"]
        self.assertEqual(agent["state"], "live")
        self.assertEqual(agent["status"], "working")

    def test_parallel_hooks_do_not_lose_notices(self):
        data = self.registry()
        second = dict(data["agents"][f"{SESSION}/maple-worker"])
        second.update({"pane": "w2:p4", "orch": ORCH, "status": "working"})
        data["agents"][f"{SESSION}/second-codex"] = second
        self.registry_path.write_text(json.dumps(data))
        self.write_herdr_state(
            **{
                "w2:p1": {"agent": "claude", "agent_status": "done"},
                "w2:p4": {"agent": "codex", "agent_status": "blocked"},
                "w2:p9": {"agent": "claude", "agent_status": "working"},
            }
        )
        items = [event_for("claude", "done"), {"event": "pane.agent_status_changed", "data": {"pane_id": "w2:p4", "agent_status": "working"}}]
        procs = [subprocess.Popen([sys.executable, str(HOOK)], cwd=self.repo, env=self.env | {"HERDR_DELAY_GET": "0.15", "HERDR_PLUGIN_EVENT": item["event"], "HERDR_PLUGIN_EVENT_JSON": json.dumps(item["data"])}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for item in items]
        outputs = [proc.communicate() + (proc.returncode,) for proc in procs]
        self.assertEqual([out[2] for out in outputs], [0, 0], outputs)
        queue = self.registry()["orchs"][ORCH]["queue"]
        self.assertCountEqual(queue, [notice("quartz-builder", "done", "w2:p1"), notice("maple-worker", "blocked", "w2:p4")])

    def test_manifest_declares_only_the_two_phase_two_events(self):
        manifest = tomllib.loads((ROOT / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual([event["on"] for event in manifest["events"]], ["pane.agent_status_changed", "pane.closed"])
        self.assertTrue(all(event["command"] == ["python3", "hook.py"] for event in manifest["events"]))


if __name__ == "__main__":
    unittest.main()
