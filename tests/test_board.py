import json
import os
import re
import subprocess
import tempfile
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

    def test_renderer_has_anchored_rows_and_project_queue_counts_at_100(self):
        lines = self.render(100).splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 2 projects · 3 orchs · 5 agents")
        self.assertEqual(lines[1], "Legend: ! blocked; * orphan; working; idle; done; unknown")
        self.assertEqual(sum(line == "copperfield · 2 queued notices" for line in lines), 1)
        self.assertEqual(sum(line == "maple-lab · 2 queued notices" for line in lines), 1)
        self.assertEqual(sum(bool(re.fullmatch(r"BLOCKED !\s+\| copperfield / blocked-spruce-worker \| codex GPT-6-Luna", line)) for line in lines), 1)
        self.assertEqual(sum(bool(re.fullmatch(r"IDLE \*\s+\| ORPHAN / orphaned-birch-agent \| claude Haiku 5.5", line)) for line in lines), 1)
        self.assertLess(next(i for i, line in enumerate(lines) if re.fullmatch(r"BLOCKED !\s+\| copperfield / blocked-spruce-worker \| codex GPT-6-Luna", line)), next(i for i, line in enumerate(lines) if re.fullmatch(r"WORKING\s+\| copperfield / willow-fixture-reader \| claude Sonnet 5.5", line)))
        self.assertLess(next(i for i, line in enumerate(lines) if re.fullmatch(r"IDLE \*\s+\| ORPHAN / orphaned-birch-agent \| claude Haiku 5.5", line)), next(i for i, line in enumerate(lines) if re.fullmatch(r"WORKING\s+\| maple-lab / cedar-worker \| codex GPT-6.1-Sol", line)))
        self.assertTrue(lines[-1].startswith("Registry: "))
        self.assertTrue(lines[-1].endswith("refreshed 12:34:56"))
        self.assertTrue(all(board.display_width(line) <= 100 for line in lines))

    def test_renderer_fits_60_columns_and_has_narrow_rows(self):
        lines = self.render(60).splitlines()
        self.assertEqual(lines[1], "Legend: ! blocked; * orphan; working; idle; done; unknown")
        self.assertEqual(sum(line == "-" * 60 for line in lines), 1)
        self.assertEqual(sum(bool(re.fullmatch(r"BLOCKED !\s+\| copperfield / blocked-spruce-worker", line)) for line in lines), 1)
        self.assertEqual(sum(bool(re.fullmatch(r"IDLE \*\s+\| ORPHAN / orphaned-birch-agent", line)) for line in lines), 1)
        self.assertTrue(all(board.display_width(line) <= 60 for line in lines))
        self.assertEqual(lines[-1].split(" · ")[-1], "refreshed 12:34:56")
        self.assertTrue(lines[-1].endswith("/registry.json · refreshed 12:34:56"))

    def test_long_names_truncate_with_one_ellipsis_without_exceeding_width(self):
        lines = self.render(60).splitlines()
        matching = [line for line in lines if line.startswith("DONE") and "…" in line]
        self.assertEqual(len(matching), 1)
        self.assertRegex(matching[0], r"^DONE\s+\| maple-lab / extraordinarily-long-ficti…$")
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
        self.assertEqual(sum(bool(re.fullmatch(r"\x1b\[1;31mBLOCKED !\x1b\[0m\s+\| copperfield / blocked-spruce-worker \| codex GPT-6-Luna", line)) for line in lines), 1)
        self.assertEqual(sum(bool(re.fullmatch(r"\x1b\[1;35mIDLE \*\x1b\[0m\s+\| \x1b\[1;35mORPHAN\x1b\[0m / orphaned-birch-agent \| claude Haiku 5.5", line)) for line in lines), 1)

    def test_q_exits_after_initial_render(self):
        view = board.Board(self.registry, width=100, color_enabled=False, clock=lambda: "12:34:56")
        view.refresh()
        output = StringIO()
        input_stream = StringIO("qx")
        with patch("plugin.board.sys.stdin", input_stream), patch("plugin.board.sys.stdout", output), patch("plugin.board.select.select", return_value=([input_stream], [], [])) as wait_for_key:
            board.run(view)
        self.assertTrue(output.getvalue().startswith("\033[H\033[2J" + view.output + "\n"))
        self.assertEqual(output.getvalue().count("ORCH BOARD"), 1)
        wait_for_key.assert_called_once_with([input_stream], [], [], 1.0)

    def test_empty_registry_has_explicit_state_and_footer(self):
        output = board.render({"version": 1, "orchs": {}, "agents": {}}, 60, False, "/fictional/registry.json", "12:34:56")
        lines = output.splitlines()
        self.assertEqual(lines[0], "ORCH BOARD · 0 projects · 0 orchs · 0 agents")
        self.assertIn("No projects or agents registered.", lines)
        self.assertTrue(lines[-1].startswith("Registry: /fictional/registry.json"))

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
        self.assertEqual(sum(bool(re.fullmatch(r"IDLE\s+\| copperfield / fresh-worker \| unknown", line)) for line in view.output.splitlines()), 1)
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
