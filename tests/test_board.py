import json
import os
import re
import fcntl
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path
import tomllib
from unittest.mock import patch
from io import StringIO

from plugin import board


FIXTURE = Path(__file__).parent / "fixtures" / "board-registry.json"
CROWDED_FIXTURE = Path(__file__).parent / "fixtures" / "board-registry-crowded.json"
CYCLE2_FIXTURE = Path(__file__).parent / "fixtures" / "board-registry-cycle2.json"


def cycle2_status_data():
    project = "/fictional/cycle2-garden"
    return {
        "version": 1,
        "orchs": {
            "session-main/pane-main": {
                "project": project, "name": "amber-orch", "pane": "pane-main", "kind": "claude",
                "gone": False, "queue": ["fictional queued notice"], "status": "idle",
            },
        },
        "agents": {
            "session-main/adopted-builder": {
                "project": project, "name": "adopted-builder", "pane": "pane-builder", "orch": "session-main/pane-main",
                "kind": "codex", "model": "GPT-X", "status": "working", "role": "build", "adopted": True,
            },
            "session-main/closed-worker": {
                "project": project, "name": "closed-worker", "pane": "pane-closed", "orch": "session-main/pane-main",
                "kind": "claude", "status": "closed", "role": "build",
            },
            "session-main/orphan-worker": {
                "project": project, "name": "orphan-worker", "pane": "pane-orphan", "orch": "session-missing/gone-orch",
                "kind": "claude", "status": "idle", "role": "explore",
            },
        },
    }


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "registry.json"
        self.registry.write_bytes(FIXTURE.read_bytes())

    def tearDown(self):
        self.temp.cleanup()

    def render(self, width=100, color=False):
        data = json.loads(self.registry.read_text())
        return board.render(data, width, color, str(self.registry), "12:34:56")

    def start_pty(self, width):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, width, 0, 0))
        env = os.environ.copy() | {"NO_COLOR": "1"}
        env["XDG_STATE_HOME"] = str(self.registry.parent)
        process = subprocess.Popen(
            ["python3", str(Path(__file__).parents[1] / "plugin" / "board.py"), "--registry", str(self.registry)],
            stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True,
        )
        os.close(slave)
        return process, master

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

    def test_renderer_has_anchored_rows_and_project_queue_counts_at_100(self):
        lines = self.render(100).splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 2 projects · 3 orchs · 5 agents")
        self.assertEqual(lines[1], "-" * 100)
        self.assertFalse(any(line.startswith("Legend:") for line in lines))
        self.assertEqual(sum(line == "copperfield · 2 queued notices" for line in lines), 1)
        self.assertEqual(sum(line == "maple-lab · 2 queued notices" for line in lines), 1)
        self.assertTrue({"kind", "workspace", "tab"}.issubset(next(iter(json.loads(self.registry.read_text())["orchs"].values()))))
        self.assertIn("! BLOCKED          | copperfield-orch > blocked-spruce-worker                    | codex GPT-6-Luna", lines)
        self.assertIn("○ IDLE *           | ORPHAN > orphaned-birch-agent                               | claude Haiku 5.5", lines)
        self.assertLess(next(i for i, line in enumerate(lines) if "! BLOCKED" in line), next(i for i, line in enumerate(lines) if "▶ WORKING" in line and "willow-fixture-reader" in line))
        self.assertLess(next(i for i, line in enumerate(lines) if "▶ WORKING" in line and "cedar-worker" in line), next(i for i, line in enumerate(lines) if "○ IDLE *" in line))
        self.assertEqual(lines[-1], "refreshed 12:34:56")
        self.assertTrue(all(board.display_width(line) <= 100 for line in lines))

    def test_cli_renders_cli_generated_cycle2_fixture_with_adopted_closed_and_orphan_rows(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parents[1] / "plugin" / "board.py"), "--once", "--width", "100", "--registry", str(CYCLE2_FIXTURE)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ORCH BOARD · 1 project · 1 orch · 2 agents", result.stdout)
        self.assertIn("orch > fictional-adopted-builder", result.stdout)
        self.assertIn("× CLOSED", result.stdout)
        self.assertIn("ORPHAN > fictional-orphan-worker", result.stdout)

    def test_renderer_uses_singular_count_labels(self):
        data = {
            "version": 1,
            "orchs": {
                "session-fictional/pane-one": {
                    "project": "/fictional/single-garden", "name": "fictional-single-orch", "gone": False,
                    "queue": ["fictional notice"], "status": "idle",
                },
            },
            "agents": {
                "session-fictional/single-worker": {
                    "project": "/fictional/single-garden", "name": "fictional-single-worker",
                    "orch": "session-fictional/pane-one", "status": "done",
                },
            },
        }
        lines = board.render(data, 100, False, "registry.json", "12:34:56").splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 1 project · 1 orch · 1 agent")
        self.assertEqual(sum(line == "single-garden · 1 queued notice" for line in lines), 1)

    def test_renderer_uses_plural_count_labels(self):
        lines = self.render(100).splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 2 projects · 3 orchs · 5 agents")
        self.assertEqual(sum(line == "copperfield · 2 queued notices" for line in lines), 1)

    def test_header_and_rows_share_separator_columns_at_100_with_color(self):
        lines = self.render(100, color=True).splitlines()
        plain = [board.ANSI_RE.sub("", line) for line in lines]
        header = next(line for line in plain if line.startswith("STATE"))
        positions = [index for index, char in enumerate(header) if char == "|"]
        rows = [line for line in plain if re.match(r"(?:!|▶|○|✓|×|\?) ", line)]
        self.assertEqual(positions, [19, 81])
        self.assertTrue(rows)
        self.assertTrue(all([index for index, char in enumerate(line) if char == "|"] == positions for line in rows))

    def test_header_and_rows_share_separator_columns_at_60(self):
        lines = self.render(60).splitlines()
        header = next(line for line in lines if line.startswith("STATE"))
        rows = [line for line in lines if re.match(r"(?:!|▶|○|✓|×|\?) ", line)]
        self.assertEqual([index for index, char in enumerate(header) if char == "|"], [12, 44])
        self.assertTrue(rows)
        self.assertTrue(all([index for index, char in enumerate(line) if char == "|"] == [12, 44] for line in rows))

    def test_footer_fits_real_timestamp_at_accepted_widths(self):
        timestamp = "2026-10-19 09:19:05 PKT"
        for width in (40, 50, 60, 84, 100):
            with self.subTest(width=width):
                footer = board.footer("/fictional/state/orch/registry.json", timestamp, width)
                self.assertLessEqual(board.display_width(footer), width)
                self.assertEqual(footer, "refreshed 09:19:05")

    def test_closed_agents_and_gone_orchs_are_not_counted_but_closed_rows_are_dim(self):
        data = json.loads(self.registry.read_text())
        data["agents"]["session-amber/worker-active"]["status"] = "closed"
        output = board.render(data, 100, True, "registry.json", "12:34:56")
        lines = output.splitlines()
        self.assertEqual(board.ANSI_RE.sub("", lines[0]), "ORCH BOARD · 2 projects · 3 orchs · 4 agents")
        closed = next(line for line in lines if "× CLOSED" in board.ANSI_RE.sub("", line))
        self.assertIn("\033[2;37m× CLOSED\033[0m", closed)
        self.assertIn("copperfield-orch > willow-fixture-reader", board.ANSI_RE.sub("", closed))
        self.assertEqual(sum("× CLOSED" in board.ANSI_RE.sub("", line) for line in lines), 1)

    def test_narrow_board_exact_rows_at_40_60_and_100_columns(self):
        data = cycle2_status_data()
        expected = {
            40: {
                "header": "ORCH · 1P · 1O · 2A",
                "rows": [
                    "○ IDLE      | amber-orch                ",
                    "▶ WORKING   | amber… > adopted-builder  ",
                    "× CLOSED    | amber-orch > closed-worker",
                    "○ IDLE *    | ORPHAN > orphan-worker    ",
                ],
                "columns": [12],
            },
            60: {
                "header": "ORCH BOARD · 1 project · 1 orch · 2 agents",
                "rows": [
                    "○ IDLE      | amber-orch                      | claude · Q:1",
                    "▶ WORKING   | amber-orch > adopted-builder    | codex GPT-X",
                    "× CLOSED    | amber-orch > closed-worker      | claude",
                    "○ IDLE *    | ORPHAN > orphan-worker          | claude",
                ],
                "columns": [12, 46],
            },
            100: {
                "header": "ORCH BOARD · 1 project · 1 orch · 2 agents",
                "rows": [
                    "○ IDLE             | amber-orch                                                       | claude · Q:1",
                    "▶ WORKING          | amber-orch > adopted-builder                                     | codex GPT-X",
                    "× CLOSED           | amber-orch > closed-worker                                       | claude",
                    "○ IDLE *           | ORPHAN > orphan-worker                                           | claude",
                ],
                "columns": [19, 86],
            },
        }
        for width, wanted in expected.items():
            with self.subTest(width=width):
                lines = board.render(data, width, False, "registry.json", "12:34:56").splitlines()
                self.assertEqual(lines[0], wanted["header"])
                header = next(line for line in lines if line.startswith("STATE"))
                self.assertEqual([i for i, char in enumerate(header) if char == "|"], wanted["columns"])
                rows = [line for line in lines if re.match(r"(?:!|▶|○|✓|×|\?) ", line)]
                self.assertEqual(rows, wanted["rows"])
                self.assertTrue(all(board.display_width(line) <= width for line in lines))

    def test_runtime_column_fits_narrow_width_and_smaller_width_degrades(self):
        data = cycle2_status_data()
        projects = board.build_projects(data)
        required_runtime = max(board.display_width(board.runtime_label(row)) for project in projects for row in project["rows"])
        required_path = max(board.path_reservation(row) for project in projects for row in project["rows"])
        for width in (30, 40, 42, 43, 44, 50, 51, 52, 53, 60, 65, 100):
            with self.subTest(width=width):
                lines = board.render(data, width, False, "registry.json", "12:34:56").splitlines()
                self.assertTrue(all(board.display_width(line) <= width for line in lines))
                header = next((line for line in lines if line.startswith("STATE")), "")
                self.assertEqual("HOST / MODEL" in header, width >= 53)
                layout = board.table_layout(width, required_runtime, required_path)
                self.assertEqual(layout[2] > 0, width >= 53)

    def test_runtime_reserves_owner_separator_and_worker_leaf_at_50_60_and_67(self):
        project = "/fictional/amber-garden"
        data = {
            "version": 1,
            "orchs": {"s/p": {"project": project, "name": "orch-owner", "gone": False, "queue": []}},
            "agents": {},
        }
        for name in ("fictional-worker-prefix-alpha-A-tail", "fictional-worker-prefix-bravo-B-tail"):
            data["agents"]["s/" + name] = {
                "project": project, "name": name, "orch": "s/p", "status": "working",
                "kind": "claude", "model": "fictional-extraordinarily-long-model-name",
            }
        expected = {
            50: {
                "layout": (11, 36, 0), "runtime": False,
                "rows": [
                    "▶ WORKING   | orch-… > fictional-wor…-alpha-A-tail",
                    "▶ WORKING   | orch-… > fictional-wor…-bravo-B-tail",
                ],
            },
            60: {
                "layout": (11, 29, 14), "runtime": True,
                "rows": [
                    "▶ WORKING   | orch-… > fictional-…ha-A-tail | claude fictio…",
                    "▶ WORKING   | orch-… > fictional-…vo-B-tail | claude fictio…",
                ],
            },
            67: {
                "layout": (11, 29, 21), "runtime": True,
                "rows": [
                    "▶ WORKING   | orch-… > fictional-…ha-A-tail | claude fictional-ext…",
                    "▶ WORKING   | orch-… > fictional-…vo-B-tail | claude fictional-ext…",
                ],
            },
            57: {
                "layout": (11, 43, 0), "runtime": False,
                "rows": [
                    "▶ WORKING   | orch-… > fictional-worker-…fix-alpha-A-tail",
                    "▶ WORKING   | orch-… > fictional-worker-…fix-bravo-B-tail",
                ],
            },
        }
        for width, wanted in expected.items():
            with self.subTest(width=width):
                state_width, path_width, runtime_width = board.table_layout(width, 26, 29)
                self.assertEqual((state_width, path_width, runtime_width), wanted["layout"])
                lines = board.render(data, width, False, "registry.json", "12:34:56").splitlines()
                header = next(line for line in lines if line.startswith("STATE"))
                self.assertEqual("HOST / MODEL" in header, wanted["runtime"])
                rows = [line for line in lines if line.startswith("▶ WORKING")]
                self.assertEqual(rows, wanted["rows"])
                self.assertTrue(all(board.display_width(line) == width for line in rows))
                self.assertIn("A-tail", rows[0])
                self.assertIn("B-tail", rows[1])
                self.assertNotEqual(rows[0], rows[1])

    def test_orphan_rows_keep_status_order(self):
        project = "/fictional/amber-garden"
        data = {
            "version": 1, "orchs": {},
            "agents": {
                "s/closed": {"project": project, "name": "fictional-closed-leaf", "orch": "s/missing", "status": "closed"},
                "s/working": {"project": project, "name": "fictional-working-leaf", "orch": "s/missing", "status": "working"},
                "s/blocked": {"project": project, "name": "fictional-blocked-leaf", "orch": "s/missing", "status": "blocked"},
            },
        }
        rows = [line for line in board.render(data, 100, False, "registry.json", "12:34:56").splitlines() if line.startswith(("! BLOCKED", "▶ WORKING", "× CLOSED"))]
        self.assertEqual([line.split("|")[0].strip() for line in rows], ["! BLOCKED *", "▶ WORKING *", "× CLOSED *"])
        self.assertEqual([line.split("|")[1].strip().rsplit(" > ", 1)[-1] for line in rows], ["fictional-blocked-leaf", "fictional-working-leaf", "fictional-closed-leaf"])

    def test_orch_groups_and_projects_have_exactly_one_blank_line_between_them(self):
        data = {
            "version": 1,
            "orchs": {
                "s/a": {"project": "/fictional/amber-garden", "name": "amber-orch", "gone": False, "queue": []},
                "s/b": {"project": "/fictional/amber-garden", "name": "birch-orch", "gone": False, "queue": []},
                "s/c": {"project": "/fictional/blue-harbor", "name": "cobalt-orch", "gone": False, "queue": []},
            },
            "agents": {
                "s/a1": {"project": "/fictional/amber-garden", "name": "amber-worker", "orch": "s/a", "status": "working"},
                "s/b1": {"project": "/fictional/amber-garden", "name": "birch-worker", "orch": "s/b", "status": "working"},
                "s/x1": {"project": "/fictional/amber-garden", "name": "orphan-one", "orch": "s/missing", "status": "idle"},
                "s/x2": {"project": "/fictional/amber-garden", "name": "orphan-two", "orch": "s/missing", "status": "idle"},
                "s/c1": {"project": "/fictional/blue-harbor", "name": "cobalt-worker", "orch": "s/c", "status": "working"},
            },
        }
        lines = board.render(data, 100, False, "registry.json", "12:34:56").splitlines()
        anchors = ["amber-worker", "birch-orch", "birch-worker", "ORPHAN > orphan-one", "ORPHAN > orphan-two", "blue-harbor · 0 queued notices"]
        indexes = [next(i for i, line in enumerate(lines) if anchor in line) for anchor in anchors]
        self.assertEqual([right - left for left, right in zip(indexes, indexes[1:])], [2, 1, 2, 1, 2])
        self.assertNotIn("\n\n\n", "\n".join(lines))

    def test_status_glyphs_render_without_legend_or_color_at_60_and_100(self):
        for width in (60, 100):
            data = json.loads(self.registry.read_text())
            data["agents"]["session-slate/worker-active"]["status"] = "unrecognized"
            output = board.render(data, width, False, "registry.json", "12:34:56")
            self.assertNotIn("Legend:", output)
            self.assertIn("○ IDLE", output)
            self.assertIn("▶ WORKING", output)
            self.assertIn("✓ DONE", output)
            self.assertIn("? UNKNOWN", output)
            self.assertIn("! BLOCKED", output)
            self.assertNotRegex(output, r"\x1b\[")

    def test_long_parent_components_keep_distinct_worker_names_at_60(self):
        data = {"version": 1, "orchs": {"s/p": {"project": "/fictional/long-project-component-name-that-needs-truncation", "name": "fictional-coordinator-with-an-extraordinarily-long-name", "gone": False, "queue": []}}, "agents": {}}
        for name in ("fictional-worker-one", "fictional-worker-two"):
            data["agents"]["s/" + name] = {"project": data["orchs"]["s/p"]["project"], "name": name, "orch": "s/p", "status": "working"}
        output = board.render(data, 60, False, "registry.json", "12:34:56")
        rows = [line for line in output.splitlines() if "▶ WORKING" in line]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows, [
            "▶ WORKING   | ficti… > fictional-worker-one  | unknown",
            "▶ WORKING   | ficti… > fictional-worker-two  | unknown",
        ])
        self.assertNotEqual(rows[0], rows[1])
        self.assertTrue(all(board.display_width(line) <= 60 for line in rows))

    def test_crowded_hierarchy_rows_drop_project_and_keep_names_at_100_and_60(self):
        data = json.loads(CROWDED_FIXTURE.read_text())
        expected = {
            100: [
                "▶ WORKING          | amber-lead-orch > fictional-amber-worker                         | claude",
                "○ IDLE             | fictional-coordinator-with-an-extraordinarily-long-name          | claude · Q:0",
                "? UNKNOWN          | ficti… > fictional-worker-with-an-ex…-name-for-narrow-board-view | claude",
                "○ IDLE *           | ORPHAN > fictional-orphan-fir-worker                             | claude",
            ],
            60: [
                "○ IDLE      | amber-lead-orch                 | claude · Q:1",
                "▶ WORKING   | amber… > fictional-amber-worker | claude",
                "○ IDLE      | amber-review-orch               | claude · Q:0",
                "○ IDLE      | amber… > fictional-i…e-reviewer | claude",
                "○ IDLE *    | ORPHAN > fictional-o…fir-worker | claude",
                "○ IDLE      | blue-lead-orch                  | claude · Q:0",
                "! BLOCKED   | blue-… > fictional-b…ed-builder | claude",
                "○ IDLE      | fictional-coordinator-with-an-… | claude · Q:0",
                "? UNKNOWN   | ficti… > fictional-w…board-view | claude",
                "○ IDLE      | copper-lead-orch                | claude · Q:0",
                "✓ DONE      | coppe… > fictional-c…ted-worker | claude",
                "○ IDLE      | copper-review-orch              | claude · Q:0",
                "▶ WORKING   | coppe… > fictional-c…r-reviewer | claude",
                "? UNKNOWN * | ORPHAN > fictional-o…ash-worker | claude",
            ],
        }
        for width, wanted_rows in expected.items():
            with self.subTest(width=width):
                lines = board.render(data, width, False, "registry.json", "12:34:56").splitlines()
                rows = [line for line in lines if re.match(r"(?:!|▶|○|✓|×|\?) ", line)]
                for wanted in wanted_rows:
                    self.assertEqual(rows.count(wanted), 1, wanted)
                self.assertTrue(all(board.display_width(line) <= width for line in lines))
                self.assertFalse(any("fictional-amber-garden >" in line or "fictional-blue-harbor >" in line or "fictional-copper-hill >" in line for line in rows))

    def test_resize_redraws_at_new_width_without_registry_change(self):
        process, master = self.start_pty(100)
        try:
            initial = self.read_pty(master, 0.3)
            self.assertIn("-" * 100, initial)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 60, 0, 0))
            resized = self.read_pty(master, 1.4)
            self.assertIn("-" * 60, resized)
            self.assertNotIn("-" * 100, resized)
            os.write(master, b"q")
            process.wait(timeout=2)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_cli_registry_uses_project_orch_agent_hierarchy(self):
        from importlib import import_module
        phase = import_module("tests.test_phase1").PhaseOne()
        phase.setUp()
        try:
            phase.reg()
            phase.spawn("fictional-worker")
            data = phase.state()
            orch = next(iter(data["orchs"].values()))
            agent = next(iter(data["agents"].values()))
            self.assertEqual(orch["name"], "orch")
            self.assertNotEqual(Path(orch["project"]).name, orch["name"])
            self.assertTrue({"kind", "workspace", "tab"}.issubset(orch))
            self.assertTrue({"kind", "model", "effort", "where", "role"}.issubset(agent))
            projects = board.build_projects(data)
            rows = [row for project in projects for row in project["rows"]]
            self.assertIn(["orch"], [row["path"] for row in rows])
            self.assertIn(["orch", "fictional-worker"], [row["path"] for row in rows])
            output = board.render(data, 100, False, "registry.json", "12:34:56")
            self.assertIn("orch > fictional-worker", output)
            self.assertNotIn("repo > orch", output)
        finally:
            phase.tearDown()

    def test_renderer_fits_60_columns_and_has_narrow_rows(self):
        lines = self.render(60).splitlines()
        self.assertEqual(lines[1], "-" * 60)
        self.assertEqual(sum(line == "-" * 60 for line in lines), 1)
        self.assertIn("HOST / MODEL", lines[2])
        self.assertTrue(any("! BLOCKED" in line and "blocked-sp…ce-worker" in line for line in lines))
        self.assertTrue(any("○ IDLE *" in line and "orphaned-birch-agent" in line for line in lines))
        self.assertTrue(all(board.display_width(line) <= 60 for line in lines))
        self.assertEqual(lines[-1], "refreshed 12:34:56")

    def test_long_names_truncate_with_one_ellipsis_without_exceeding_width(self):
        lines = self.render(60).splitlines()
        matching = [line for line in lines if "✓ DONE" in line and "extraordinarily-long-fictional-agent-name-for-truncation-check" not in line]
        self.assertEqual(len(matching), 1)
        self.assertIn("…ion-check", matching[0])
        self.assertIn("…", matching[0])
        self.assertLessEqual(board.display_width(matching[0]), 60)

    def test_no_color_contains_no_ansi_sequences(self):
        output = self.render(100, color=False)
        self.assertNotRegex(output, r"\x1b\[")
        self.assertTrue(any(line == "" for line in output.splitlines()))

    def test_no_color_environment_disables_terminal_styles(self):
        class TerminalBuffer(StringIO):
            def isatty(self):
                return True

        output = TerminalBuffer()
        with patch.dict(os.environ, {"NO_COLOR": ""}), patch("plugin.board.sys.stdout", output):
            board.main(["--once", "--width", "60", "--registry", str(self.registry)])
        self.assertNotRegex(output.getvalue(), r"\x1b\[")

    def test_blocked_and_orphan_rows_use_distinct_styles_and_markers(self):
        lines = self.render(100, color=True).splitlines()
        self.assertTrue(any("\x1b[1;31m! BLOCKED\x1b[0m" in line and "blocked-spruce-worker" in line for line in lines))
        self.assertTrue(any("\x1b[1;35m○ IDLE *\x1b[0m" in line and "\x1b[1;35mORPHAN\x1b[0m" in line for line in lines))
        self.assertTrue(any("\x1b[1;34m▶ WORKING\x1b[0m" in line for line in lines))
        self.assertTrue(any("\x1b[32m✓ DONE\x1b[0m" in line for line in lines))

    def test_q_exits_after_initial_render(self):
        process, master = self.start_pty(100)
        try:
            self.read_pty(master, 0.3)
            os.write(master, b"xq")
            process.wait(timeout=2)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)

    def test_empty_registry_has_explicit_state_and_footer(self):
        output = board.render({"version": 1, "orchs": {}, "agents": {}}, 60, False, "/fictional/registry.json", "12:34:56")
        lines = output.splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 0 projects · 0 orchs · 0 agents")
        self.assertIn("No projects or agents registered.", lines)
        self.assertEqual(lines[-1], "refreshed 12:34:56")

    def test_refresh_only_changes_when_registry_mtime_changes(self):
        view = board.Board(self.registry, width=100, color_enabled=False, clock=lambda: "12:34:56")
        initial = view.refresh()
        self.assertTrue(initial)
        self.assertFalse(view.refresh())
        data = json.loads(self.registry.read_text())
        data["agents"]["session-amber/worker-new"] = {
            "project": "/fictional/copperfield", "name": "fresh-worker", "orch": "session-amber/pane-1", "status": "idle"
        }
        self.registry.write_text(json.dumps(data))
        stamp = self.registry.stat().st_mtime_ns + 2_000_000_000
        import os
        os.utime(self.registry, ns=(stamp, stamp))
        self.assertTrue(view.refresh())
        self.assertEqual(view.refreshed_at, "12:34:56")
        self.assertTrue(any("○ IDLE" in line and "copperfield-orch > fresh-worker" in line for line in view.output.splitlines()))
        self.assertFalse(view.refresh())

    def test_manifest_declares_board_action_and_pane_commands(self):
        manifest = tomllib.loads((Path(__file__).parents[1] / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["actions"], [
            {"id": "board", "title": "Open orch board", "contexts": ["pane"], "command": ["python3", "board.py", "--open"]},
            {"id": "board-full", "title": "Orch board, full screen", "contexts": ["pane"], "command": ["python3", "board.py", "--open", "--placement", "overlay"]},
        ])
        self.assertEqual(manifest["panes"], [{
            "id": "board", "title": "Orch board", "placement": "split", "command": ["python3", "board.py"]
        }])

    def test_open_action_targets_current_pane_without_changing_plugin_cwd(self):
        responses = [subprocess.CompletedProcess([], 0, '{"result":{"pane":{"pane_id":"fixture-board"}}}', "")]
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane"}), patch("plugin.board.subprocess.run", side_effect=responses) as run:
            board.open_board()
        self.assertEqual(run.call_args_list[0].args[0], [
            "herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board",
            "--placement", "split", "--target-pane", "fixture-pane", "--direction", "right",
        ])
        manifest = tomllib.loads((Path(__file__).parents[1] / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["panes"][0]["command"], ["python3", "board.py"])

    def test_full_board_open_action_uses_overlay_without_split_arguments(self):
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane", "ORCH_BOARD_DIRECTION": "left"}), patch("plugin.board.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
            board.open_board("overlay")
        self.assertEqual(run.call_args.args[0], [
            "herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board", "--placement", "overlay",
        ])

    def test_full_board_exact_rows_at_160_and_100_columns(self):
        data = json.loads(CYCLE2_FIXTURE.read_text())
        expected = {
            160: [
                "○ IDLE             | orch                                                                                                                | claude · Q:0",
                "▶ WORKING          | orch > fictional-adopted-builder                                                                                    | codex fictional-model",
                "× CLOSED           | orch > fictional-closed-worker                                                                                      | claude",
                "▶ WORKING *        | ORPHAN > fictional-orphan-worker                                                                                    | claude",
            ],
            100: [
                "○ IDLE             | orch                                                    | claude · Q:0",
                "▶ WORKING          | orch > fictional-adopted-builder                        | codex fictional-model",
                "× CLOSED           | orch > fictional-closed-worker                          | claude",
                "▶ WORKING *        | ORPHAN > fictional-orphan-worker                        | claude",
            ],
        }
        for width, wanted_rows in expected.items():
            with self.subTest(width=width):
                lines = board.render(data, width, False, "registry.json", "12:34:56").splitlines()
                rows = [line for line in lines if re.match(r"(?:!|▶|○|✓|×|\?) ", line)]
                self.assertEqual(rows, wanted_rows)
                self.assertTrue(all(board.display_width(line) <= width for line in lines))

    def test_open_action_direction_defaults_right_and_accepts_down(self):
        for environment, direction in (({}, "right"), ({"ORCH_BOARD_DIRECTION": "down"}, "down")):
            with self.subTest(direction=direction), patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane", **environment}), patch("plugin.board.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
                board.open_board()
            self.assertEqual(run.call_args.args[0][-1], direction)

    def test_open_action_rejects_invalid_direction_before_herdr_call(self):
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane", "ORCH_BOARD_DIRECTION": "left"}), patch("plugin.board.subprocess.run") as run:
            with self.assertRaisesRegex(SystemExit, "ORCH_BOARD_DIRECTION must be 'right' or 'down'"):
                board.open_board()
        run.assert_not_called()

    def test_cli_accepts_width_below_40_and_clips_each_line(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parents[1] / "plugin" / "board.py"), "--once", "--width", "30", "--registry", str(self.registry)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(board.display_width(line) <= 30 for line in result.stdout.splitlines()))


if __name__ == "__main__":
    unittest.main()
