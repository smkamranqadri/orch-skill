import json
import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import tomllib
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from plugin import board


ROOT = Path(__file__).resolve().parents[1]
FAKE_HERDR = ROOT / "tests" / "fixtures" / "herdr" / "board-bin"


def sample_registry():
    project = "/fictional/orch-skill"
    return {
        "version": 1,
        "orchs": {
            "session-a/p1": {"project": project, "name": "orch-claude", "pane": "p1", "status": "idle", "queue": ["notice one", "notice two"]},
            "session-b/p1": {"project": project, "name": "orch-codex", "pane": "p2", "status": "working", "queue": [], "paused": {"count": 1}},
        },
        "agents": {
            "session-a/closedrows": {"project": project, "name": "closedrows", "pane": "a1", "orch": "session-a/p1", "status": "done"},
            "session-a/rel-reviewer": {"project": project, "name": "rel-reviewer", "pane": "a2", "orch": "session-a/p1", "status": "closed", "closed_at": 999},
            "session-b/worker": {"project": project, "name": "other-session-worker", "pane": "b1", "orch": "session-b/p1", "status": "working"},
            "session-a/orphan": {"project": project, "name": "orphan-worker", "pane": "a3", "orch": "session-gone/gone", "status": "blocked"},
        },
    }


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps(sample_registry()))

    def tearDown(self):
        self.temp.cleanup()

    def render(self, width=100, enabled=False, data=None, now=1000, titles=None):
        with patch.dict(os.environ, {"HERDR_SESSION": "session-a"}):
            return board.render(data or json.loads(self.registry.read_text()), width, enabled,
                                str(self.registry), "2026-10-19 12:34:56", now=now, pane_titles=titles)

    def board_cli_env(self, **overrides):
        calls = self.root / "orch-board-herdr-calls.jsonl"
        return self.clean_env() | {
            "PATH": str(FAKE_HERDR) + os.pathsep + self.clean_env().get("PATH", ""),
            "ORCH_BOARD_HERDR_CALLS": str(calls),
            "ORCH_BOARD_AGENT_STATUS": "missing",
            "NO_COLOR": "1",
            "HERDR_ENV": "",
        } | overrides

    def clean_env(self):
        env = os.environ.copy()
        for name in list(env):
            if name.startswith("HERDR_") or name == "XDG_STATE_HOME":
                env.pop(name, None)
        home = self.root / "home"
        home.mkdir(exist_ok=True)
        env["HOME"] = str(home)
        return env

    def calls(self, env):
        path = Path(env["ORCH_BOARD_HERDR_CALLS"])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_orch(self, *args, env=None):
        return subprocess.run([sys.executable, str(ROOT / "plugin" / "orch"), *args],
                              text=True, capture_output=True, env=env or self.board_cli_env())

    def test_header_columns_projects_orch_sections_and_plain_agent_names(self):
        rendered = self.render(titles={"session-a/p1": "Fictional task title"})
        lines = rendered.splitlines()
        plain = [line.strip() for line in lines]
        self.assertEqual(plain[:3], [
            "orch board v1.0.0", "refresh: 1s · last: 12:34:56",
            "Status: All · 2 orchs · 3 agents",
        ])
        self.assertEqual(plain[4], "Name                            Status         Project           Title")
        self.assertTrue(plain[5].startswith("─"))
        self.assertIn("orch-skill · 2 queued", plain)
        first_orch = next(i for i, line in enumerate(lines) if "▾ orch-claude" in line)
        second_orch = next(i for i, line in enumerate(lines) if "▾ orch-codex" in line)
        self.assertLess(plain.index("orch-skill · 2 queued"), first_orch)
        orch_row = lines[first_orch][2:-2]
        self.assertEqual((orch_row[:30].strip(), orch_row[32:44].strip(), orch_row[46:62].strip(), orch_row[64:].strip()),
                         ("▾ orch-claude", "idle  Q:2", "orch-skill", "Fictional task title"))
        self.assertEqual([line.strip().split()[0:2] for line in lines[first_orch + 1:first_orch + 3]],
                         [["├", "closedrows"], ["└", "rel-reviewer"]])
        self.assertIn("PAUSED 1", lines[second_orch])
        self.assertLess(second_orch, next(i for i, line in enumerate(lines) if "other-session-worker" in line))
        self.assertIn("orphans", plain)
        self.assertIn("* orphan-worker", "\n".join(plain))
        self.assertEqual(plain[-2:], ["", "q quit"])
        self.assertNotIn("refreshed", "\n".join(plain))

    def test_header_cells_start_at_data_columns_at_supported_widths(self):
        titles = {"session-a/p1": "Fictional task title"}
        expected = {
            160: ((2, 34, 49, 67), (30, 13, 16, 92), "▾ orch-claude", "Fictional task title"),
            100: ((2, 34, 49, 67), (30, 13, 16, 32), "▾ orch-claude", "Fictional task title"),
            67: ((2, 26, 41, 59), (22, 13, 16, 6), "▾ orch-claude", "Ficti…"),
            55: ((2, 16, 31, 43), (12, 13, 10, 10), "▾ orch-clau…", "Fictional…"),
        }
        for width in (160, 100, 67, 55):
            with self.subTest(width=width):
                lines = self.render(width=width, titles=titles).splitlines()
                header = lines[4]
                offsets, cell_widths, expected_name, expected_title = expected[width]
                name, status, project, title = cell_widths
                self.assertEqual(tuple(header.find(cell) for cell in ("Name", "Status", "Project", "Title")), offsets)
                row = next(line for line in lines if line[offsets[1]:offsets[1] + status].strip() == "idle  Q:2")
                self.assertEqual(tuple(row[offset:offset + cell_width].strip() for offset, cell_width in zip(offsets, (name, status, project, title))),
                                 (expected_name, "idle  Q:2", "orch-skill", expected_title))

    def test_narrow_status_column_keeps_status_and_queue_count(self):
        lines = self.render(width=55).splitlines()
        row = next(line for line in lines if "▾ orch-codex" in line)
        status_start, status_width = 16, 13
        self.assertEqual(row[status_start:status_start + status_width].strip(), "PAUSED 1  Q:0")

        data = sample_registry()
        data["orchs"]["session-b/p1"].pop("paused")
        lines = self.render(width=55, data=data).splitlines()
        row = next(line for line in lines if "▾ orch-codex" in line)
        self.assertEqual(row[status_start:status_start + status_width].strip(), "working  Q:0")

    def test_status_column_keeps_large_queue_counts_and_paused_counts_at_all_widths(self):
        data = {"version": 1, "orchs": {
            "s/working": {"project": "/fictional/status-garden", "name": "working-orch", "status": "working", "queue": ["n"] * 10},
            "s/paused": {"project": "/fictional/status-garden", "name": "paused-orch", "status": "blocked", "queue": ["n"] * 10, "paused": {"count": 10}},
        }, "agents": {}}
        for width in (160, 100, 67, 55, 40):
            with self.subTest(width=width):
                rows = [line.strip() for line in self.render(width=width, data=data).splitlines()]
                self.assertTrue(any("working  Q:10" in line for line in rows))
                self.assertTrue(any("PAUSED 10  Q:10" in line for line in rows))

    def test_each_project_has_heading_even_without_queue_and_gone_queues_remain(self):
        data = {"version": 1, "orchs": {
            "s/live": {"project": "/fictional/quiet-garden", "name": "quiet-orch", "status": "idle", "queue": []},
            "s/gone": {"project": "/fictional/queued-harbor", "name": "gone-orch", "gone": True, "queue": ["a", "b", "c"]},
        }, "agents": {}}
        lines = [line.strip() for line in self.render(data=data).splitlines()]
        self.assertIn("quiet-garden", lines)
        self.assertIn("queued-harbor · 3 queued", lines)
        self.assertNotIn("gone-orch", "\n".join(lines))

    def test_all_gone_project_keeps_queue_after_last_closed_child_expires(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/retained-harbor", "name": "gone-orch", "gone": True,
            "queue": ["notice"],
        }}, "agents": {"s/a": {
            "project": "/fictional/retained-harbor", "name": "expired-worker",
            "orch": "s/p", "status": "closed", "closed_at": 399,
        }}}
        lines = [line.strip() for line in self.render(data=data, now=1000).splitlines()]
        self.assertIn("retained-harbor · 1 queued", lines)
        self.assertNotIn("gone-orch", "\n".join(lines))
        self.assertNotIn("expired-worker", "\n".join(lines))

    def test_empty_registry_and_expired_only_orphan_keep_explicit_states(self):
        empty = self.render(data={"version": 1, "orchs": {}, "agents": {}}).splitlines()
        self.assertIn("No projects or agents registered.", [line.strip() for line in empty])
        expired = self.render(data={"version": 1, "orchs": {}, "agents": {"s/a": {
            "project": "/fictional/orphan-garden", "name": "expired-orphan", "orch": "gone/p",
            "status": "closed", "closed_at": 399,
        }}}, now=1000).splitlines()
        self.assertIn("No live orchs or agents.", [line.strip() for line in expired])
        self.assertFalse(any("expired-orphan" in line for line in expired))

    def test_gone_owner_classifies_its_agent_as_orphan(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/gone-garden", "name": "gone-owner", "gone": True, "queue": [],
        }}, "agents": {"s/a": {
            "project": "/fictional/gone-garden", "name": "orphan-worker", "orch": "s/p", "status": "blocked",
        }}}
        lines = self.render(data=data).splitlines()
        self.assertIn("orphans", [line.strip() for line in lines])
        self.assertTrue(any("* orphan-worker" in line for line in lines))

    def test_closed_row_expiry_redraws_on_unchanged_registry_mtime(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/refresh-garden", "name": "refresh-orch", "status": "idle", "queue": [],
        }}, "agents": {"s/a": {
            "project": "/fictional/refresh-garden", "name": "closed-worker", "orch": "s/p",
            "status": "closed", "closed_at": 1000,
        }}}
        self.registry.write_text(json.dumps(data))
        view = board.Board(self.registry, 100, False)
        now = [1599.5]
        view.now = lambda: now[0]
        self.assertTrue(view.refresh())
        mtime = self.registry.stat().st_mtime_ns
        self.assertIn("closed-worker", view.output)
        now[0] = 1600.1
        self.assertTrue(view.refresh())
        self.assertNotIn("closed-worker", view.output)
        self.assertEqual(self.registry.stat().st_mtime_ns, mtime)

    def test_closed_rows_from_both_close_paths_expire_and_missing_timestamps_stay_hidden(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/retention-garden", "name": "retention-orch", "status": "idle", "queue": [],
        }}, "agents": {
            "s/worktree-closed": {"project": "/fictional/retention-garden", "name": "worktree-closed", "orch": "s/p", "where": "worktree", "state": "closed", "status": "closed", "closed_at": 1000},
            "s/pane-closed": {"project": "/fictional/retention-garden", "name": "pane-closed", "orch": "s/p", "where": "pane", "state": "closed", "status": "closed", "closed_at": 1000},
            "s/cleanup-no-time": {"project": "/fictional/retention-garden", "name": "cleanup-no-time", "orch": "s/p", "state": "cleanup", "status": "done"},
            "s/closed-no-time": {"project": "/fictional/retention-garden", "name": "closed-no-time", "orch": "s/p", "state": "closed", "status": "done"},
        }}
        self.registry.write_text(json.dumps(data))
        view = board.Board(self.registry, 100, False, clock=lambda: "12:34:56")
        now = [1599]
        view.now = lambda: now[0]
        self.assertTrue(view.refresh())
        self.assertIn("worktree-closed", view.output)
        self.assertIn("pane-closed", view.output)
        self.assertNotIn("cleanup-no-time", view.output)
        self.assertNotIn("closed-no-time", view.output)
        now[0] = 1600.1
        self.assertTrue(view.refresh())
        self.assertNotIn("worktree-closed", view.output)
        self.assertNotIn("pane-closed", view.output)

    def test_refresh_skips_unchanged_mtime_and_rereads_after_change(self):
        view = board.Board(self.registry, 100, False, clock=lambda: "12:34:56")
        data = json.loads(self.registry.read_text())
        data["agents"]["session-a/fresh"] = {
            "project": "/fictional/orch-skill", "name": "fresh-worker", "orch": "session-a/p1", "status": "idle",
        }
        with patch.object(Path, "read_text", wraps=self.registry.read_text) as read_text:
            self.assertTrue(view.refresh())
            self.assertFalse(view.refresh())
            self.assertEqual(read_text.call_count, 1)
            original_stamp = view.refreshed_at
            self.registry.write_text(json.dumps(data))
            future = self.registry.stat().st_mtime_ns + 2_000_000_000
            os.utime(self.registry, ns=(future, future))
            self.assertTrue(view.refresh())
            self.assertEqual(read_text.call_count, 2)
            self.assertEqual(view.refreshed_at, original_stamp)
            self.assertIn("fresh-worker", view.output)
            self.assertFalse(view.refresh())

    def test_refresh_ticks_header_without_rereading_unchanged_registry(self):
        times = iter(("2026-10-20 12:34:56", "2026-10-20 12:34:57", "2026-10-20 12:34:58"))
        view = board.Board(self.registry, 100, False, clock=lambda: next(times))
        with patch.object(Path, "read_text", wraps=self.registry.read_text) as read_text:
            self.assertTrue(view.refresh())
            self.assertIn("last: 12:34:56", view.output)
            self.assertTrue(view.refresh())
            self.assertIn("last: 12:34:57", view.output)
            self.assertTrue(view.refresh())
            self.assertIn("last: 12:34:58", view.output)
            self.assertEqual(read_text.call_count, 1)

    def test_pty_header_ticks_twice_without_clearing_board(self):
        process, master = self.start_pty(100)
        try:
            output = bytearray()
            deadline = time.monotonic() + 8
            distinct = set()
            while time.monotonic() < deadline and len(distinct) < 3:
                readable, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
                if not readable:
                    break
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
                distinct = set(re.findall(rb"last: (\d{2}:\d{2}:\d{2})", output))
            self.assertGreaterEqual(len(distinct), 3, output.decode(errors="replace"))
            rendered = output.decode(errors="replace")
            self.assertEqual(rendered.count("\033[2J"), 1)
            self.assertGreaterEqual(rendered.count("\033[2;1H"), 2)
            os.write(master, b"q")
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_header_tick_preserves_cursor_and_exit_leaves_cursor_below_frame(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/cursor-garden", "name": "cursor-orch", "status": "idle", "queue": [],
        }}, "agents": {}}
        self.registry.write_text(json.dumps(data))
        process, master = self.start_pty(100)
        output = bytearray()
        deadline = time.monotonic() + 8
        stamps = set()
        try:
            while time.monotonic() < deadline and len(stamps) < 2:
                readable, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
                if not readable:
                    break
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
                stamps = set(re.findall(rb"last: (\d{2}:\d{2}:\d{2})", output))
            self.assertGreaterEqual(len(stamps), 2, output.decode(errors="replace"))
            os.write(master, b"q")
            process.wait(timeout=3)
            while select.select([master], [], [], 0)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
            payload = output.decode(errors="replace")
            self.assertRegex(payload, re.compile(r"\033\[s\033\[2;1H.*?\033\[u", re.S))
            expected_row = len(board.render(data, 100, False, str(self.registry), "12:34:56").splitlines()) + 1
            self.assertTrue(payload.endswith(f"\033[{expected_row};1H"), payload[-100:])
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_manifest_declares_board_pane_command(self):
        manifest = tomllib.loads((ROOT / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["panes"], [{
            "id": "board", "title": "Orch board", "placement": "split", "command": ["python3", "board.py"],
        }])

    def test_fixture_full_frame_snapshots_at_55_and_100_columns(self):
        data = json.loads((ROOT / "tests" / "fixtures" / "board-registry-golden.json").read_text())
        for width in (55, 100):
            with self.subTest(width=width):
                actual = "\n".join(line.rstrip() for line in self.render(width=width, data=data).splitlines())
                expected = (ROOT / "tests" / "fixtures" / f"board-frame-{width}.txt").read_text().rstrip("\n")
                self.assertEqual(actual, expected)

    def test_status_colors_are_applied_to_rendered_rows(self):
        data = {"version": 1, "orchs": {}, "agents": {
            "s/blocked": {"project": "/fictional/colors", "name": "blocked-agent", "status": "blocked"},
            "s/working": {"project": "/fictional/colors", "name": "working-agent", "status": "working"},
            "s/done": {"project": "/fictional/colors", "name": "done-agent", "status": "done"},
            "s/unknown": {"project": "/fictional/colors", "name": "unknown-agent", "status": "mystery"},
            "s/closed": {"project": "/fictional/colors", "name": "closed-agent", "status": "closed", "closed_at": 999},
        }}
        with patch.dict(os.environ, {"TERM": "xterm", "COLORTERM": ""}):
            output = self.render(data=data, enabled=True)
        for fragment in ("\033[1;31mblocked\033[0m", "\033[32mworking\033[0m",
                         "\033[32mdone\033[0m", "\033[33munknown\033[0m", "\033[2;37mclosed\033[0m"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, output)

    def test_short_long_worker_names_remain_distinct_at_100_columns(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/names", "name": "name-orch", "status": "idle", "queue": [],
        }}, "agents": {}}
        for name in ("fictional-worker-alpha", "fictional-worker-bravo"):
            data["agents"]["s/" + name] = {"project": "/fictional/names", "name": name, "orch": "s/p", "status": "working"}
        rows = [line for line in self.render(data=data, width=100).splitlines() if "fictional-worker-" in line]
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0], rows[1])
        self.assertIn("fictional-worker-alpha", rows[0])
        self.assertIn("fictional-worker-bravo", rows[1])

    def test_cli_registry_builds_project_orch_agent_hierarchy(self):
        from importlib import import_module
        phase = import_module("tests.test_phase1").PhaseOne()
        phase.setUp()
        try:
            phase.reg()
            phase.spawn("fictional-worker")
            data = phase.state()
            orch = data["orchs"]["session-a/p1"]
            agent = data["agents"]["session-a/fictional-worker"]
            self.assertEqual(orch["name"], "orch")
            self.assertNotEqual(Path(orch["project"]).name, orch["name"])
            self.assertTrue({"kind", "workspace", "tab"}.issubset(orch))
            self.assertTrue({"kind", "model", "effort", "where", "role"}.issubset(agent))
            rows = [row for project in board.build_projects(data) for row in project["rows"]]
            self.assertIn(["orch"], [row["path"] for row in rows])
            self.assertIn(["orch", "fictional-worker"], [row["path"] for row in rows])
            output = board.render(data, 100, False, "registry.json", "12:34:56")
            self.assertIn("fictional-worker", output)
            self.assertNotIn("orch > fictional-worker", output)
        finally:
            phase.tearDown()

    def test_closed_rows_expire_at_ten_minutes_and_closed_agents_are_not_counted(self):
        data = sample_registry()
        data["agents"]["session-a/rel-reviewer"]["closed_at"] = 399
        lines = self.render(data=data, now=1000).splitlines()
        self.assertIn("Status: All · 2 orchs · 3 agents", "\n".join(lines))
        self.assertNotIn("rel-reviewer", "\n".join(lines))
        data["agents"]["session-a/rel-reviewer"]["closed_at"] = 400
        lines = self.render(data=data, now=1000).splitlines()
        self.assertIn("rel-reviewer", "\n".join(lines))

    def test_orch_queue_and_pause_are_rendered_in_status_column(self):
        plain = [line.strip() for line in self.render().splitlines()]
        orch = next(line for line in plain if line.startswith("▾ orch-claude"))
        paused = next(line for line in plain if line.startswith("▾ orch-codex"))
        self.assertIn("idle  Q:2", orch)
        self.assertIn("PAUSED 1", paused)

    def test_count_labels_use_singular_and_plural_forms(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/one-garden", "name": "one-orch", "status": "idle", "queue": [],
        }}, "agents": {"s/a": {
            "project": "/fictional/one-garden", "name": "one-agent", "orch": "s/p", "status": "done",
        }}}
        lines = [line.strip() for line in self.render(data=data).splitlines()]
        self.assertIn("Status: All · 1 orch · 1 agent", lines)
        data["agents"].clear()
        lines = [line.strip() for line in self.render(data=data).splitlines()]
        self.assertIn("Status: All · 1 orch · 0 agents", lines)
        data["orchs"].clear()
        lines = [line.strip() for line in self.render(data=data).splitlines()]
        self.assertIn("Status: All · 0 orchs · 0 agents", lines)

    def test_orphans_keep_status_order_and_session_ownership(self):
        data = {"version": 1, "orchs": {
            "s/p": {"project": "/fictional/one-garden", "name": "owner", "status": "idle", "queue": []},
            "other-session/p": {"project": "/fictional/one-garden", "name": "other-owner", "status": "idle", "queue": []},
        }, "agents": {
            "s/worker": {"project": "/fictional/one-garden", "name": "owned-worker", "orch": "s/p", "status": "working"},
            "other-session/worker": {"project": "/fictional/one-garden", "name": "separate-session-worker", "orch": "other-session/p", "status": "blocked"},
            "s/orphan-working": {"project": "/fictional/one-garden", "name": "orphan-working", "orch": "s/missing", "status": "working"},
            "s/orphan-blocked": {"project": "/fictional/one-garden", "name": "orphan-blocked", "orch": "s/missing", "status": "blocked"},
        }}
        lines = self.render(data=data).splitlines()
        self.assertIn("separate-session-worker", "\n".join(lines))
        self.assertIn("owned-worker", "\n".join(lines))
        self.assertLess(next(i for i, line in enumerate(lines) if "other-owner" in line),
                        next(i for i, line in enumerate(lines) if "separate-session-worker" in line))
        blocked = next(i for i, line in enumerate(lines) if "orphan-blocked" in line)
        working = next(i for i, line in enumerate(lines) if "orphan-working" in line)
        self.assertLess(blocked, working)

    def test_rows_fit_55_67_100_and_160_columns_with_two_column_margin(self):
        for width in (55, 67, 100, 160):
            with self.subTest(width=width):
                lines = self.render(width).splitlines()
                self.assertTrue(all(board.display_width(line) <= width for line in lines))
                self.assertTrue(all(line.startswith("  ") for line in lines if line))
                self.assertTrue(all(board.display_width(line) == width for line in lines if line))
                if width == 55:
                    self.assertIn("* orphan-wo…", "\n".join(lines))

    def test_color_modes_and_no_color(self):
        cases = (("16", "\033[1;34m"), ("256", "\033[1;38;5;111m"), ("truecolor", "\033[1;38;2;130;156;255m"))
        for mode, expected in cases:
            with self.subTest(mode=mode):
                self.assertEqual(board.color("orch", "app", True, mode), expected + "orch\033[0m")
        self.assertEqual(board.color("idle", "dim", False, "truecolor"), "idle")
        self.assertNotIn("\033[", self.render(enabled=False))

    def test_no_color_environment_disables_styles_on_a_tty(self):
        class TerminalBuffer(StringIO):
            def isatty(self):
                return True

        output = TerminalBuffer()
        with patch.dict(os.environ, {"NO_COLOR": ""}), patch("plugin.board.sys.stdout", output), patch("plugin.board.read_pane_titles", return_value={}):
            board.main(["--once", "--width", "60", "--registry", str(self.registry)])
        self.assertNotIn("\033[", output.getvalue())

    def test_resize_reformats_without_registry_change(self):
        view = board.Board(self.registry, 100, False)
        with patch.dict(os.environ, {"HERDR_ENV": ""}):
            self.assertTrue(view.refresh())
            original = view.output
            self.assertTrue(view.set_width(55))
        self.assertNotEqual(view.output, original)
        self.assertTrue(all(board.display_width(line) == 55 for line in view.output.splitlines() if line))

    def test_pane_titles_parse_fallback_and_timeout(self):
        payload = {"result": {"panes": [
            {"pane_id": "p1", "terminal_title_stripped": "First title"},
            {"pane_id": "p2", "label": "Label fallback"},
            {"pane_id": "p3", "terminal_title": "Terminal fallback"},
        ]}}
        with patch.dict(os.environ, {"HERDR_SESSION": "session-a"}):
            self.assertEqual(board.pane_titles_from_payload(payload), {
                "session-a/p1": "First title", "session-a/p2": "Label fallback", "session-a/p3": "Terminal fallback",
            })
        with patch("plugin.board.subprocess.run", side_effect=subprocess.TimeoutExpired("herdr", 1)) as run:
            self.assertEqual(board.read_pane_titles(), {})
        self.assertEqual(run.call_args.kwargs["timeout"], 1)

    def test_pane_titles_are_session_scoped_and_sanitized(self):
        payload = {"result": {"panes": [
            {"pane_id": "p1", "terminal_title": "\033[31mFirst\033[0m\nsecond\r\tline"},
        ]}}
        with patch.dict(os.environ, {"HERDR_SESSION": "session-a"}):
            self.assertEqual(board.pane_titles_from_payload(payload), {"session-a/p1": "Firstsecondline"})
            data = {"version": 1, "orchs": {
                "session-a/p1": {"project": "/fictional/title-garden", "name": "current-orch", "pane": "p1", "status": "idle", "queue": []},
                "session-b/p1": {"project": "/fictional/title-garden", "name": "other-orch", "pane": "p1", "status": "idle", "queue": []},
            }, "agents": {
                "session-a/w": {"project": "/fictional/title-garden", "name": "current-worker", "pane": "p1", "orch": "session-a/p1", "status": "working"},
                "session-b/w": {"project": "/fictional/title-garden", "name": "other-worker", "pane": "p1", "orch": "session-b/p1", "status": "working"},
            }}
            output = self.render(data=data, titles={"session-a/p1": "Current title", "session-b/p1": "Foreign title"})
        self.assertIn("Current title", output)
        self.assertNotIn("Foreign title", output)
        self.assertEqual(output.count("Current title"), 2)

    def test_unrecognized_status_renders_unknown(self):
        data = {"version": 1, "orchs": {}, "agents": {"s/a": {
            "project": "/fictional/unknown-garden", "name": "odd-worker", "status": "unrecognized",
        }}}
        lines = self.render(data=data).splitlines()
        row = next(line for line in lines if "odd-worker" in line)
        self.assertIn("unknown", row)
        self.assertNotIn("unrecognized", row)

    def test_closing_and_cleanup_states_override_stale_done_status(self):
        closing = {"kind": "AGENT", "node": {"name": "worker-alpha", "status": "done", "state": "closing"}}
        cleanup = {"kind": "AGENT", "node": {"name": "worker-bravo", "status": "done", "state": "cleanup"}}
        self.assertEqual(board.status_cell(closing, False), "closing")
        self.assertEqual(board.status_cell(cleanup, False), "cleanup")

    def test_board_refreshes_title_changes_without_registry_change(self):
        view = board.Board(self.registry, 100, False, clock=lambda: "2026-10-19 12:34:56")
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_SESSION": "session-a"}), patch(
            "plugin.board.read_pane_titles", side_effect=[{"session-a/p1": "First title"}, {"session-a/p1": "Updated title"}]
        ) as reader:
            self.assertTrue(view.refresh())
            self.assertTrue(view.refresh())
        self.assertEqual(reader.call_count, 2)
        self.assertIn("Updated title", view.output)

    def test_no_tty_opens_overlay_and_passes_no_board_options(self):
        env = self.board_cli_env()
        result = self.run_orch("board", "--once", "--width", "67", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(env), [["plugin", "action", "invoke", "board-full", "--plugin", "orch"]])

    def test_tty_non_agent_runs_board_in_place_and_passes_options(self):
        env = self.board_cli_env()
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board", "--once", "--width", "55"],
                                       stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
            output = self.read_pty(master, 3)
            process.wait(timeout=3)
            error = process.stderr.read()
            process.stderr.close()
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(process.returncode, 0, error)
        self.assertIn("orch board v1.0.0", output)
        self.assertTrue(all(board.display_width(line) == 55 for line in output.splitlines() if line.strip()))
        self.assertEqual(self.calls(env), [["pane", "current", "--current"], ["agent", "get", "fixture-pane"]])

    def test_tty_agent_pane_opens_overlay(self):
        env = self.board_cli_env(ORCH_BOARD_AGENT_STATUS="working")
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board", "--once"],
                                       stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
            process.wait(timeout=3)
            error = process.stderr.read()
            process.stderr.close()
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(process.returncode, 0, error)
        self.assertEqual(self.calls(env), [["pane", "current", "--current"], ["agent", "get", "fixture-pane"],
                                           ["plugin", "action", "invoke", "board-full", "--plugin", "orch"]])

    def test_tty_unknown_agent_status_still_keeps_agent_pane_safe(self):
        env = self.board_cli_env(ORCH_BOARD_AGENT_STATUS="unknown")
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board"],
                                       stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
            process.wait(timeout=3)
            error = process.stderr.read()
            process.stderr.close()
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(process.returncode, 0, error)
        self.assertEqual(self.calls(env), [["pane", "current", "--current"], ["agent", "get", "fixture-pane"],
                                           ["plugin", "action", "invoke", "board-full", "--plugin", "orch"]])

    def test_agent_lookup_uncertainty_and_present_done_status_route_to_overlay(self):
        for response, status in (("transport", "working"), ("malformed", "working"), ("empty", "working"), ("", "done")):
            with self.subTest(response=response, status=status):
                env = self.board_cli_env(ORCH_BOARD_AGENT_RESPONSE=response, ORCH_BOARD_AGENT_STATUS=status)
                master, slave = pty.openpty()
                try:
                    process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board", "--once"],
                                               stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
                    process.wait(timeout=3)
                    error = process.stderr.read()
                    process.stderr.close()
                finally:
                    os.close(master)
                    os.close(slave)
                self.assertEqual(process.returncode, 0, error)
                self.assertEqual(self.calls(env)[-1], ["plugin", "action", "invoke", "board-full", "--plugin", "orch"])

    def test_explicit_agent_absence_allows_in_place_board(self):
        env = self.board_cli_env(ORCH_BOARD_AGENT_RESPONSE="absent")
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board", "--once", "--width", "55"],
                                       stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
            output = self.read_pty(master, 3)
            process.wait(timeout=3)
            error = process.stderr.read()
            process.stderr.close()
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(process.returncode, 0, error)
        self.assertIn("orch board v1.0.0", output)
        self.assertNotIn("plugin", [call[0] for call in self.calls(env)[-1:]])

    def test_overlay_failure_prints_exact_command(self):
        env = self.board_cli_env(ORCH_BOARD_OVERLAY_FAIL="1")
        result = self.run_orch("board", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip().splitlines()[-1], "herdr plugin action invoke board-full --plugin orch")

    def test_missing_herdr_prints_diagnostic_and_fallback(self):
        env = self.board_cli_env(PATH="/no-such-herdr-path")
        result = self.run_orch("board", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("herdr", result.stderr.lower())
        self.assertIn("herdr plugin action invoke board-full --plugin orch", result.stdout)

    def test_missing_herdr_during_tty_probe_falls_back_without_traceback(self):
        env = self.board_cli_env(PATH="/no-such-herdr-path")
        master, slave = pty.openpty()
        try:
            process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "orch"), "board", "--once"],
                                       stdin=slave, stdout=slave, stderr=subprocess.PIPE, text=True, env=env)
            output = self.read_pty_until(master, "herdr plugin action invoke board-full --plugin orch", timeout=4)
            process.wait(timeout=3)
            error = process.stderr.read()
            process.stderr.close()
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(process.returncode, 127)
        self.assertIn("could not launch herdr", error)
        self.assertNotIn("Traceback", error)
        self.assertIn("herdr plugin action invoke board-full --plugin orch", output)

    def test_q_exits_and_width_30_remains_clipped(self):
        master, slave = pty.openpty()
        process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "board.py"), "--registry", str(self.registry)],
                                   stdin=slave, stdout=slave, stderr=slave, env=self.clean_env() | {"NO_COLOR": "1"})
        try:
            output = self.read_pty(master, 1)
            self.assertIn("q quit", output)
            os.write(master, b"q")
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)
        result = subprocess.run([sys.executable, str(ROOT / "plugin" / "board.py"), "--once", "--width", "30", "--registry", str(self.registry)],
                               text=True, capture_output=True, env=self.clean_env() | {"NO_COLOR": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(board.display_width(line) <= 30 for line in result.stdout.splitlines()))

    def read_pty(self, master, duration):
        output = bytearray()
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
            if not readable:
                break
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                break
        return output.decode(errors="replace")

    def start_pty(self, width):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, width, 0, 0))
        process = subprocess.Popen([sys.executable, str(ROOT / "plugin" / "board.py"), "--registry", str(self.registry)],
                                   stdin=slave, stdout=slave, stderr=slave, env=self.clean_env() | {"NO_COLOR": "1"})
        os.close(slave)
        return process, master

    def read_pty_until(self, master, expected, timeout=8):
        output = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if expected.encode() in output:
                return output.decode(errors="replace")
            readable, _, _ = select.select([master], [], [], max(0, deadline - time.monotonic()))
            if not readable:
                break
            try:
                output.extend(os.read(master, 65536))
            except OSError:
                break
        self.fail(f"PTY output did not contain expected marker {expected!r}: {output.decode(errors='replace')!r}")

    def test_resize_redraws_live_board_at_pty_width(self):
        process, master = self.start_pty(100)
        try:
            initial = self.read_pty_until(master, "─" * 96)
            self.assertIn("orch board v1.0.0", initial)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 60, 0, 0))
            resized = self.read_pty_until(master, "─" * 56)
            self.assertNotIn("─" * 96, resized)
            os.write(master, b"q")
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_adding_agent_clears_old_footer_from_blank_separator(self):
        data = {"version": 1, "orchs": {"s/p": {
            "project": "/fictional/pty-garden", "name": "pty-orch", "status": "idle", "queue": [],
        }}, "agents": {}}
        self.registry.write_text(json.dumps(data))
        process, master = self.start_pty(100)
        screen = [[" "] * 100 for _ in range(24)]

        def apply(output):
            y = x = 0
            pending_wrap = False
            tokens = re.split(r"(\033\[[0-?]*[ -/]*[@-~])", output)
            for token in tokens:
                if token.startswith("\033["):
                    command = token[2:]
                    if command == "H": y = x = 0; pending_wrap = False
                    elif command == "2J": screen[:] = [[" "] * 100 for _ in range(24)]; y = x = 0; pending_wrap = False
                    elif command == "K": screen[y][x:] = [" "] * (100 - x)
                    elif command == "J":
                        screen[y][x:] = [" "] * (100 - x)
                        for row in range(y + 1, 24): screen[row] = [" "] * 100
                    elif command.endswith("H"):
                        row, column = (int(value) for value in command[:-1].split(";"))
                        y, x, pending_wrap = row - 1, column - 1, False
                    continue
                for char in token:
                    if char == "\r": x = 0; pending_wrap = False
                    elif char == "\n": y = min(23, y + 1); x = 0; pending_wrap = False
                    elif char >= " ":
                        if pending_wrap: y = min(23, y + 1); x = 0; pending_wrap = False
                        screen[y][x] = char
                        if x == 99: pending_wrap = True
                        else: x += 1

        try:
            initial = self.read_pty_until(master, "q quit")
            apply(initial)
            data["agents"]["s/worker"] = {
                "project": "/fictional/pty-garden", "name": "new-agent", "orch": "s/p", "status": "working",
            }
            self.registry.write_text(json.dumps(data))
            future = self.registry.stat().st_mtime_ns + 2_000_000_000
            os.utime(self.registry, ns=(future, future))
            update = self.read_pty_until(master, "q quit")
            self.assertIn("new-agent", update)
            apply(update)
            lines = ["".join(row).strip() for row in screen]
            self.assertEqual(lines.count("q quit"), 1, lines)
            os.write(master, b"q")
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_board_plugin_actions_are_stable(self):
        manifest = tomllib.loads((ROOT / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["actions"], [
            {"id": "board", "title": "Open orch board", "contexts": ["pane"], "command": ["python3", "board.py", "--open"]},
            {"id": "board-full", "title": "Orch board, full screen", "contexts": ["pane"], "command": ["python3", "board.py", "--open", "--placement", "overlay"]},
        ])
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane"}), patch("plugin.board.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
            board.open_board("overlay")
        self.assertEqual(run.call_args.args[0], ["herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board", "--placement", "overlay"])

    def test_open_board_missing_herdr_reports_command_and_returns_nonzero(self):
        from contextlib import redirect_stderr, redirect_stdout
        stdout, stderr = StringIO(), StringIO()
        command = "herdr plugin pane open --plugin orch --entrypoint board --placement overlay"
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane"}), \
             patch("plugin.board.subprocess.run", side_effect=FileNotFoundError("herdr missing")), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                board.open_board("overlay")
        self.assertEqual(raised.exception.code, 127)
        self.assertIn("herdr missing", stderr.getvalue())
        self.assertEqual(stdout.getvalue().strip(), command)

    def test_split_board_open_keeps_direction_and_target_behavior(self):
        for direction in ("right", "down"):
            with self.subTest(direction=direction), patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane", "ORCH_BOARD_DIRECTION": direction}), patch("plugin.board.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
                board.open_board()
            self.assertEqual(run.call_args.args[0], ["herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board", "--placement", "split", "--target-pane", "fixture-pane", "--direction", direction])
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane", "ORCH_BOARD_DIRECTION": "left"}), patch("plugin.board.subprocess.run") as run:
            with self.assertRaisesRegex(SystemExit, "ORCH_BOARD_DIRECTION must be 'right' or 'down'"):
                board.open_board()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
