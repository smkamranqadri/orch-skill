import json
import os
import re
import fcntl
import pty
import select
import struct
import subprocess
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
        self.assertEqual(lines[1], "Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan")
        self.assertEqual(sum(line == "copperfield · 2 queued notices" for line in lines), 1)
        self.assertEqual(sum(line == "maple-lab · 2 queued notices" for line in lines), 1)
        self.assertTrue({"kind", "workspace", "tab"}.issubset(next(iter(json.loads(self.registry.read_text())["orchs"].values()))))
        self.assertTrue(any("! BLOCKED" in line and "copperfield > copperfield… > blocked-spruce-worker" in line for line in lines))
        self.assertTrue(any("○ IDLE *" in line and "maple-lab > ORPHAN > orphaned-birch-agent" in line for line in lines))
        self.assertLess(next(i for i, line in enumerate(lines) if "! BLOCKED" in line), next(i for i, line in enumerate(lines) if "▶ WORKING" in line and "willow-fixture-reader" in line))
        self.assertLess(next(i for i, line in enumerate(lines) if "○ IDLE *" in line), next(i for i, line in enumerate(lines) if "▶ WORKING" in line and "cedar-worker" in line))
        self.assertTrue(lines[-1].startswith("Registry: "))
        self.assertTrue(lines[-1].endswith("refreshed 12:34:56"))
        self.assertTrue(all(board.display_width(line) <= 100 for line in lines))

    def test_header_and_rows_share_separator_columns_at_100_with_color(self):
        lines = self.render(100, color=True).splitlines()
        plain = [board.ANSI_RE.sub("", line) for line in lines]
        header = next(line for line in plain if line.startswith("STATE"))
        positions = [index for index, char in enumerate(header) if char == "|"]
        rows = [line for line in plain if re.match(r"(?:!|▶|○|✓|\?) ", line)]
        self.assertEqual(positions, [19, 72])
        self.assertTrue(rows)
        self.assertTrue(all([index for index, char in enumerate(line) if char == "|"] == positions for line in rows))

    def test_header_and_rows_share_separator_columns_at_60(self):
        lines = self.render(60).splitlines()
        header = next(line for line in lines if line.startswith("STATE"))
        rows = [line for line in lines if re.match(r"(?:!|▶|○|✓|\?) ", line)]
        self.assertEqual([index for index, char in enumerate(header) if char == "|"], [19])
        self.assertTrue(rows)
        self.assertTrue(all([index for index, char in enumerate(line) if char == "|"] == [19] for line in rows))

    def test_footer_fits_real_timestamp_at_accepted_widths(self):
        timestamp = "2026-10-19 09:19:05 PKT"
        for width in (40, 50, 60, 84, 100):
            with self.subTest(width=width):
                footer = board.footer("/fictional/state/orch/registry.json", timestamp, width)
                self.assertLessEqual(board.display_width(footer), width)
                self.assertIn("registry.json", footer)
                self.assertTrue(footer.endswith("09:19" if width == 40 else "09:19:05" if width < 75 else timestamp))

    def test_status_glyphs_and_legend_survive_no_color_at_60_and_100(self):
        for width in (60, 100):
            data = json.loads(self.registry.read_text())
            data["agents"]["session-slate/worker-active"]["status"] = "unrecognized"
            output = board.render(data, width, False, "registry.json", "12:34:56")
            self.assertIn("○ idle", output)
            self.assertIn("▶ work", output)
            self.assertIn("✓ done", output)
            self.assertIn("? unknown", output)
            self.assertIn("! blocked", output)
            self.assertIn("* orphan", output)
            self.assertIn("! BLOCKED", output)
            self.assertIn("▶ WORKING", output)
            self.assertIn("✓ DONE", output)
            self.assertIn("? UNRECOGNIZED", output)
            self.assertNotRegex(output, r"\x1b\[")

    def test_long_parent_components_keep_distinct_worker_names_at_60(self):
        data = {"version": 1, "orchs": {"s/p": {"project": "/fictional/long-project-component-name-that-needs-truncation", "name": "fictional-coordinator-with-an-extraordinarily-long-name", "gone": False, "queue": []}}, "agents": {}}
        for name in ("fictional-worker-one", "fictional-worker-two"):
            data["agents"]["s/" + name] = {"project": data["orchs"]["s/p"]["project"], "name": name, "orch": "s/p", "status": "working"}
        output = board.render(data, 60, False, "registry.json", "12:34:56")
        rows = [line for line in output.splitlines() if "▶ WORKING" in line]
        self.assertEqual(len(rows), 2)
        self.assertIn("fictional-worker-one", rows[0])
        self.assertIn("fictional-worker-two", rows[1])
        self.assertNotEqual(rows[0], rows[1])
        self.assertTrue(all(board.display_width(line) <= 60 for line in rows))

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
            self.assertIn(["repo", "orch"], [row["path"] for row in rows])
            self.assertIn(["repo", "orch", "fictional-worker"], [row["path"] for row in rows])
            output = board.render(data, 100, False, "registry.json", "12:34:56")
            self.assertIn("repo > orch > fictional-worker", output)
        finally:
            phase.tearDown()

    def test_renderer_fits_60_columns_and_has_narrow_rows(self):
        lines = self.render(60).splitlines()
        self.assertEqual(lines[1], "Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan")
        self.assertEqual(sum(line == "-" * 60 for line in lines), 1)
        self.assertTrue(any("! BLOCKED" in line and "blocked-spruce-worker" in line for line in lines))
        self.assertTrue(any("○ IDLE *" in line and "orphaned-birch-agent" in line for line in lines))
        self.assertTrue(all(board.display_width(line) <= 60 for line in lines))
        self.assertEqual(lines[-1].split(" · ")[-1], "12:34:56")
        self.assertTrue(lines[-1].endswith("registry.json · 12:34:56"))

    def test_long_names_truncate_with_one_ellipsis_without_exceeding_width(self):
        lines = self.render(60).splitlines()
        matching = [line for line in lines if "✓ DONE" in line and "extraordinarily-long-fictional-agent-name-for-truncation-check" not in line]
        self.assertEqual(len(matching), 1)
        self.assertIn("extraordinarily-long-fi…", matching[0])
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
            os.write(master, b"qx")
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
        self.assertTrue(lines[-1].startswith("Reg: "))

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
        self.assertTrue(any("○ IDLE" in line and "copperfield > copperfield-orch > fresh-worker" in line for line in view.output.splitlines()))
        self.assertFalse(view.refresh())

    def test_manifest_declares_board_action_and_pane_commands(self):
        manifest = tomllib.loads((Path(__file__).parents[1] / "plugin" / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["actions"], [{
            "id": "board", "title": "Open orch board", "contexts": ["pane"], "command": ["python3", "board.py", "--open"]
        }])
        self.assertEqual(manifest["panes"], [{
            "id": "board", "title": "Orch board", "placement": "split", "command": ["python3", "board.py"]
        }])

    def test_open_action_targets_the_current_pane_and_project(self):
        responses = [
            subprocess.CompletedProcess([], 0, "/fictional/copperfield\n", ""),
            subprocess.CompletedProcess([], 0, '{"result":{"pane":{"pane_id":"fixture-board"}}}', ""),
        ]
        with patch.dict(os.environ, {"HERDR_ENV": "1", "HERDR_PANE_ID": "fixture-pane"}), patch("plugin.board.subprocess.run", side_effect=responses) as run:
            board.open_board()
        self.assertEqual(run.call_args_list[0].args[0], ["git", "rev-parse", "--show-toplevel"])
        self.assertEqual(run.call_args_list[1].args[0], [
            "herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board",
            "--placement", "split", "--target-pane", "fixture-pane", "--direction", "right", "--cwd", "/fictional/copperfield",
        ])


if __name__ == "__main__":
    unittest.main()
