#!/usr/bin/env python3
import copy
import fcntl
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import pty
from pathlib import Path
import shutil
import select
import time
import struct
import subprocess
import termios
import sys
import tempfile
import textwrap
import tomllib
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "skills/orch/plugin"
FIXTURE = ROOT / "tests/fixtures/board"
loader = importlib.machinery.SourceFileLoader("orch_plugin_board", str(PLUGIN / "board"))
spec = importlib.util.spec_from_loader(loader.name, loader)
board = importlib.util.module_from_spec(spec)
loader.exec_module(board)
NOW = dt.datetime(2026, 10, 18, 12, tzinfo=dt.timezone.utc)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root / "Moonwell run"
        shutil.copytree(FIXTURE, self.run)
        self.env = dict(os.environ, HOME=str(self.root / "home"), XDG_CACHE_HOME=str(self.root / "cache"),
                        PYTHONDONTWRITEBYTECODE="1", TZ="UTC", ORCH_RUN_DIR="", ORCH_USAGE_CACHE_DIR="")
        self.env = {k: v for k, v in self.env.items() if not k.startswith("HERDR_")}
        bindir = self.root / "bin"
        bindir.mkdir()
        stub = bindir / "herdr"
        stub.write_text('#!/bin/sh\necho forbidden > "$CALLS"\nexit 99\n')
        stub.chmod(0o755)
        self.env.update(PATH=str(bindir) + os.pathsep + self.env["PATH"], CALLS=str(self.root / "forbidden-call"))
        self.cache = self.root / "cache/orch"
        self.cache.mkdir(parents=True)
        shutil.copyfile(self.run / "usage.json", self.cache / "usage.json")
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.data = board.snapshot(self.run, NOW)

    def render(self, width=80, **kwargs):
        rows, _ = board.render(self.data, width, **kwargs)
        return "\n".join(text for text, _ in rows)

    def command(self, *args, env=None):
        return subprocess.run([sys.executable, str(PLUGIN / "board"), *map(str, args)],
                              env=env or self.env, capture_output=True, text=True, timeout=10)

    def test_widths_and_rows(self):
        for width in (80, 140):
            text = self.render(width)
            lines = text.splitlines()
            self.assertTrue(all(board.cells(line) <= width for line in lines))
            self.assertEqual(lines[0], "Orch | Moonwell Lab | 2026-10-18 12:00:00 UTC")
            self.assertRegex(text, r"(?m)^Next action \(captain \(wQ:p1\)\): Verify ember, then release silt\.$")
            self.assertEqual(sum("ember [working]" in line for line in lines), 1)
            self.assertEqual(sum("fern [blocked]" in line for line in lines), 1)
            self.assertEqual(sum("opal [closed]" in line for line in lines), 1)
            self.assertEqual(sum("silt [queued]" in line for line in lines), 1)
            self.assertRegex(text, r"(?m)^ember -> silt$")
            self.assertRegex(text, r"(?m)^Recent$")
            self.assertRegex(text, r"(?m)^\[2026-10-17\]$")
            self.assertRegex(text, r"(?m)^\[Today 2026-10-18\]$")
            self.assertEqual(self.data["warnings"], [])
        self.assertRegex(self.render(80), r"(?m)^\| ember \[working\].*\| fern \[blocked\].*\|$")
        self.assertRegex(self.render(140), r"(?m)^\| ember \[working\].*\| fern \[blocked\].*\| opal \[closed\].*\|$")

    def test_cache_and_needs(self):
        self.assertEqual(self.data["usage"], "claude 25%/40% · codex 90%/54% ASK · cmd ? | cached 11:00:00")
        self.assertEqual(self.data["needs"], ["11:41:00 ember reported 19m ago, not verified",
                         "11:42:00 fern is blocked and needs you",
                         "waiting on user: approve fern's fixture choice", "usage ASK: codex"])
        strip = self.render().split("Needs-you: ", 1)[1].split("\nTasks", 1)[0]
        self.assertEqual(" ".join(line.strip() for line in strip.splitlines()), "; ".join(self.data["needs"]))

    def test_closed_title_evidence_and_card(self):
        opal = next(t for t in self.data["tasks"] if t["name"] == "opal")
        self.assertEqual(opal["title"], "Preserve the moonstone report")
        self.assertEqual(opal["context"], "61% used")
        self.assertEqual(opal["pane"], "none")
        self.assertEqual(opal["owner"], "captain (wQ:p1)")
        self.assertEqual(opal["age"], "1d 01h | since 2026-10-17 10:31:00")
        self.assertEqual(opal["evidence"], "verified a1: report checked | proof .orch/opal/report.md")
        with (self.run / "events.log").open("a") as stream:
            stream.write("2026-10-18T11:59:00Z silt done | An earlier cycle | ctx 10% used\n")
        self.assertEqual(board.snapshot(self.run, NOW)["tasks"][3]["state"], "queued")
        card = self.render(card="opal")
        self.assertRegex(card, r"(?m)^opal \[closed\]$")
        self.assertRegex(card, r"(?m)^Preserve the moonstone report$")
        self.assertRegex(card, r"(?m)^Pane: none$")
        self.assertRegex(card, r"(?m)^handoff: .orch/opal/handoff.md$")
        self.assertRegex(card, r"(?m)^2026-10-17 10:31:00 opal gone: none$")
        self.assertRegex(card, r"(?m)^2026-10-17 10:22:00 orchestrator woken: opal$")

    def test_registration_owner_wins_and_legacy(self):
        (self.run / "agents.txt").write_text("ember orch=harbor\nfern orch=harbor\n")
        data = board.snapshot(self.run, NOW)
        self.assertEqual(data["tasks"][0]["owner"], "harbor")
        (self.run / "orchestrator").write_text("captain\n")
        (self.run / "agents.txt").write_text("ember\n")
        self.assertEqual(board.snapshot(self.run, NOW)["tasks"][0]["owner"], "captain")
        self.assertEqual(board.owner_name("wR:p8", {}), "name unavailable (wR:p8)")

    def test_live_owner_names_are_read_only_and_optional(self):
        with patch.object(board, "herdr") as call:
            self.assertEqual(board.live_owner_names(), {})
            call.assert_not_called()
        response = {"result": {"agents": [{"name": "harbor", "pane_id": "wQ:p1"},
                                            {"name": None, "pane_id": "wR:p1"}]}}
        with patch.dict(os.environ, {"HERDR_ENV": "1"}), patch.object(board, "herdr") as call:
            call.return_value.stdout = json.dumps(response)
            names = board.live_owner_names()
            self.assertEqual(names, {"wQ:p1": "harbor"})
            call.assert_called_once_with("agent", "list")
            data = board.snapshot(self.run, NOW, live_names=names)
            self.assertEqual(data["tasks"][0]["owner"], "harbor (wQ:p1)")
            call.side_effect = subprocess.TimeoutExpired("herdr", 15)
            self.assertEqual(board.live_owner_names(), {})

    def test_owner_refresh_uses_one_minute_cache(self):
        screen = Mock()
        screen.getmaxyx.return_value = (24, 80)
        screen.getch.side_effect = [-1, -1, ord("q")]
        with patch.object(board.curses, "curs_set"), patch.object(board.curses, "has_colors", return_value=False), \
             patch.object(board.time, "monotonic", side_effect=[100, 100, 120, 161, 161]), \
             patch.object(board, "live_owner_names", return_value={"wQ:p1": "harbor"}) as owners, \
             patch.object(board, "snapshot", wraps=board.snapshot) as snap:
            board.ui(screen, self.run)
            self.assertEqual(owners.call_count, 2)
            self.assertEqual(snap.call_count, 3)
            for call in snap.call_args_list:
                self.assertEqual(call.kwargs, {"live_names": {"wQ:p1": "harbor"}})

    def test_empty_and_diagnostics(self):
        empty = self.root / "absent"
        (self.cache / "usage.json").unlink()
        data = board.snapshot(empty, NOW)
        self.assertEqual(data["needs"], [])
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["warnings"], ["ledger.md missing or unreadable"])
        text = "\n".join(t for t, _ in board.render(data)[0])
        self.assertRegex(text, r"(?m)^Next action: none$")
        self.assertRegex(text, r"(?m)^Tasks\nnone\nRecent\nnone$")
        self.assertRegex(text, r"(?m)^Needs-you: none$")
        ledger_path = self.run / "ledger.md"
        ledger_path.write_text(ledger_path.read_text().replace("| ember | wQ:p1 |", "| ember |"))
        self.assertEqual(board.snapshot(self.run, NOW)["warnings"], ["ledger: malformed task row"])
        shutil.copyfile(FIXTURE / "ledger.md", ledger_path)
        with (self.run / "events.log").open("a") as stream:
            stream.write("2026-10-17 malformed\n")
        (self.run / "agents.txt").write_text("ember invalid fields\n")
        data = board.snapshot(self.run, NOW)
        self.assertEqual(data["warnings"], ["events.log: 1 unparsed line(s)", "invalid agent registration: ember invalid fields"])

    def test_missing_cache_and_dates(self):
        (self.cache / "usage.json").unlink()
        data = board.snapshot(self.run, NOW)
        self.assertEqual(data["usage"], "none")
        self.assertEqual(board.when(dt.datetime(2025, 1, 1, 1, 2, 3, tzinfo=dt.timezone.utc), NOW),
                         "2025-01-01 01:02:03")
        self.assertEqual(board.when(NOW, NOW), "12:00:00")
        self.assertEqual(board.clean("\x1b\x07"), "none")
        self.assertEqual(board.clean("`-`"), "none")
        for cache in ("[]", '{"claude":3}', '{"collected_at":"oops"}', "{broken"):
            (self.cache / "usage.json").write_text(cache)
            self.assertEqual(board.snapshot(self.run, NOW)["usage"], "none")
        for text in ("月" * 100, "cafe\u0301 " * 100):
            self.assertTrue(all(board.cells(line) <= 36 for line in board.wrap(text, 36)))

    def test_explicit_titles_and_run_override(self):
        path = self.run / "ledger.md"
        text = path.read_text().replace("| owns |", "| owns | task |")
        text = text.replace("|" + "---|" * 11, "|" + "---|" * 12)
        for filename, title in (("engine.py", "Ember task"), ("foliage.py", "Fern task"),
                                ("notes.md", "Opal task"), ("layers.py", "Silt task")):
            text = text.replace(filename + " |", filename + " | " + title + " |")
        path.write_text(text)
        self.assertEqual([t["title"] for t in board.snapshot(self.run, NOW)["tasks"]],
                         ["Ember task", "Fern task", "Opal task", "Silt task"])
        result = self.command("--plain", env=dict(self.env, ORCH_RUN_DIR=str(self.run)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"(?m)^Orch \| Moonwell Lab \| .*$")
        missing = self.command("--open", env=dict(self.env, HERDR_ENV="1"))
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(missing.stderr, "orch board: board action needs a pane context or ORCH_RUN_DIR\n")

    def legacy_run(self):
        destination = self.root / "legacy"
        shutil.copytree(ROOT / "tests/fixtures/board-legacy", destination)
        return destination / "moonwell.reports/orch"

    def test_legacy_brief_title_before_task_and_chrome(self):
        directory = self.legacy_run()
        data = board.snapshot(directory, NOW)
        task = data["tasks"][0]
        self.assertEqual(task["name"], "leaf-queue")
        self.assertEqual(task["title"], "Resume leaf queue (#143 + #128)")
        for width in (80, 140):
            text = "\n".join(t for t, _ in board.render(data, width)[0])
            self.assertRegex(text, r"(?m)^\| Resume leaf queue \(#143 \+ #128\) +\|.*$")
            self.assertRegex(text, r"(?m)^2026-10-09 13:43:19 leaf-queue done: Resume leaf queue \(#143 \+ #128\)$")
            self.assertNotIn("leaf-queu…", text)
        path = directory / "ledger.md"
        text = path.read_text().replace("| last event |", "| last event | task |")
        text = text.replace("|" + "---|" * 8, "|" + "---|" * 9)
        text = text.replace("merged; worktree and branch removed |", "merged; worktree and branch removed | Task fallback |")
        path.write_text(text)
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"], "Resume leaf queue (#143 + #128)")
        brief = directory.parent / "leaf-queue/brief-resume.md"
        brief.write_text("An introduction.\n## Not the task title\n# Brief: First task heading\n# Second heading\n")
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"], "First task heading")
        brief.write_text("An introduction.\n## No task heading here\n")
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"], "Task fallback")
        brief.unlink()
        (directory / "none").write_text("# Incorrect title from a placeholder path\n")
        self.assertEqual(board.brief_title(directory, None), "none")
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"], "Task fallback")
        path.write_text(text.replace("| Task fallback |", "| none |"))
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"],
                         "⌘ Command Code · leaf-queu… · fixture-flash-(latest)")
        absolute = self.root / "absolute-brief.md"
        absolute.write_text("# Brief: Absolute task heading\n")
        path.write_text(text.replace("../moonwell.reports/leaf-queue/brief-resume.md", str(absolute)))
        self.assertEqual(board.snapshot(directory, NOW)["tasks"][0]["title"], "Absolute task heading")

    def test_legacy_owner_regex_and_header_next(self):
        directory = self.legacy_run()
        data = board.snapshot(directory, NOW)
        self.assertEqual(data["nexts"], [("none", "none - the run is complete; optional checks only."),
                         ("name unavailable (w2:p1T)", "SESSION CLOSED; keep the reports.")])
        text = "\n".join(t for t, _ in board.render(data, 140)[0])
        self.assertRegex(text, r"(?m)^Next action: none - the run is complete; optional checks only\.$")
        self.assertRegex(text, r"(?m)^Next action \(name unavailable \(w2:p1T\)\): SESSION CLOSED; keep the reports\.$")
        self.assertNotIn("Next action (none)", text)
        self.assertNotIn("archived leaf-queue", text)
        path = directory / "ledger.md"
        path.write_text(path.read_text().replace("by the Claude orchestrator (pane w2:p1T)", "by captain, w2:p1T"))
        self.assertEqual(board.snapshot(directory, NOW)["nexts"][1][0], "captain (w2:p1T)")

    def test_legacy_ages_at_day_boundary(self):
        data = board.snapshot(self.legacy_run(), NOW)
        self.assertEqual(data["tasks"][0]["age"], "8d 22h | since 2026-10-09 13:43:19")
        self.assertEqual(data["needs"][0], "2026-10-07 06:29:00 session-bell finished 11d 05h ago, no verdict marked")
        self.assertEqual(board.age(24 * 3600 - 1), "23h59m")
        self.assertEqual(board.age(24 * 3600), "1d 00h")
        self.assertEqual(board.age(269 * 3600 + 31 * 60), "11d 05h")
        path = self.run / "events.log"
        with path.open("a") as stream:
            stream.write("2026-10-18T11:59:00Z ember mark:reported a1 | recent report | proof -\n")
        self.assertEqual(board.snapshot(self.run, NOW)["tasks"][0]["age"], "0h20m | since 11:40:00")

    def test_legacy_recent_clip_and_needs_hanging(self):
        data = board.snapshot(self.legacy_run(), NOW)
        full = "2026-10-07 06:29:00 session-bell done: ⌘ Command Code · session-bell · fixture-flash-(latest)"
        for width in (80, 140):
            text = "\n".join(t for t, _ in board.render(data, width)[0])
            lines = text.splitlines()
            recent = lines[lines.index("Recent") + 1:-1]
            self.assertEqual(len(recent), 4)
            self.assertEqual(recent[1], full if width == 140 else full[:79] + "…")
            self.assertTrue(all(board.cells(line) <= width for line in lines))
            needs_start = next(i for i, line in enumerate(lines) if line.startswith("Needs-you:"))
            needs = lines[needs_start:lines.index("Tasks")]
            self.assertTrue(all(line.startswith(" " * 11) for line in needs[1:]))
            self.assertEqual(" ".join(line.strip() for line in needs), "Needs-you: " + "; ".join(data["needs"]))
            expected = textwrap.wrap("Needs-you: " + "; ".join(data["needs"]), width=width,
                                     subsequent_indent=" " * 11, break_long_words=False, break_on_hyphens=False)
            self.assertEqual(needs, expected)
        card = "\n".join(t for t, _ in board.render(data, 80, card="session-bell")[0])
        self.assertIn(full, " ".join(card.splitlines()))
        self.assertEqual(board.clip("月" * 50, 80), "月" * 39 + "…")
        self.assertEqual(board.hanging("Needs-you: " + "x" * 100, 80, " " * 11),
                         ["Needs-you:", " " * 11 + "x" * 68 + "…"])

    def test_fixture_separator_counts(self):
        fixtures = [FIXTURE / "ledger.md", ROOT / "tests/fixtures/board-legacy/moonwell.reports/orch/ledger.md"]
        for fixture in fixtures:
            rows = [board.watch.split_row(line) for line in fixture.read_text().splitlines() if line.startswith("|")]
            self.assertTrue(rows)
            self.assertTrue(all(len(row) == len(rows[0]) for row in rows))
        self.assertEqual(len(board.watch.split_row((FIXTURE / "ledger.md").read_text().splitlines()[8])), 11)

    def test_hook_is_consumed_and_truncated_by_merged_watcher(self):
        watcher = board.watch.Watcher(str(self.run))
        self.assertEqual(Path(watcher.signal), self.cache / "events.signal")
        result = self.hook("pane.agent_status_changed", {"pane_id": "wQ:p2", "agent_status": "blocked"})
        self.assertEqual(result.returncode, 0, result.stderr)
        watcher.read_signal()
        self.assertEqual(watcher.signalled, {"wQ:p2": "blocked"})
        with Path(watcher.signal).open("a") as stream:
            stream.write(json.dumps({"pane": "padding", "padding": "x" * (1 << 20)}) + "\n")
        result = self.hook("pane.closed", {"pane_id": "wQ:p2"})
        self.assertEqual(result.returncode, 0, result.stderr)
        watcher.read_signal()
        self.assertEqual(watcher.signalled["wQ:p2"], None)
        self.assertEqual(Path(watcher.signal).stat().st_size, 0)
        self.assertEqual(watcher.signal_pos, 0)

    def test_graph_order_cycles_and_selection(self):
        tasks = list(reversed(self.data["tasks"]))
        levels = list(board.layers(tasks))
        self.assertEqual([[t["name"] for t in level] for level in levels],
                         [["opal", "fern", "ember"], ["silt"]])
        tasks = copy.deepcopy(tasks)
        tasks[-1]["depends"] = ["silt"]
        self.assertEqual([len(level) for level in board.layers(tasks)], [2, 2])
        rows, positions = board.render(self.data, 80, selected="fern")
        self.assertEqual(set(positions), {"ember", "fern", "opal", "silt"})
        self.assertTrue(any("fern [blocked]" in t and "> fern" in t for t, _ in rows))
        self.assertTrue(any(s == "blocked:selected" for _, spans in rows for _, _, s in spans))

    def test_plain_readonly_and_repeat(self):
        (self.run / "watcher.pid").write_text("987654321\n")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        for width in (80, 140):
            first = self.command(self.run, "--plain", "--width", width)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stderr, "")
            self.assertTrue(all(board.cells(line) <= width for line in first.stdout.splitlines()))
            self.assertRegex(first.stdout, r"(?m)^Orch \| Moonwell Lab \| \d{4}-\d\d-\d\d .*$")
        processes = [subprocess.Popen([sys.executable, str(PLUGIN / "board"), str(self.run), "--plain"],
                                     env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            out, err = process.communicate(timeout=10)
            self.assertEqual((process.returncode, err), (0, b""))
            self.assertTrue(out.startswith(b"Orch | Moonwell Lab | "))
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_curses_terminal_transitions(self):
        for width in (80, 140):
            for background in ("15;0", "0;15"):
                master, slave = pty.openpty()
                try:
                    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 60, width, 0, 0))
                    destination = self.root / (str(width) + "-" + background + ".json")
                    log = self.root / "terminal.log"
                    with log.open("wb") as stream:
                        process = subprocess.Popen([sys.executable, str(ROOT / "tests/orch-plugin-terminal.py"),
                                                    str(PLUGIN / "board"), str(self.run), str(destination)],
                                                   env=dict(self.env, TERM="xterm-256color", COLORFGBG=background),
                                                   stdin=slave, stdout=slave, stderr=stream)
                        deadline = time.monotonic() + 10
                        while process.poll() is None and time.monotonic() < deadline:
                            if select.select([master], [], [], 0.1)[0]:
                                stream.write(os.read(master, 65536))
                        if process.poll() is None:
                            process.kill()
                        self.assertEqual(process.wait(timeout=2), 0, log.read_text())
                    frames = json.loads(destination.read_text())
                    self.assertEqual(len(frames), 6)
                    for frame in frames:
                        self.assertTrue(frame["lines"][-1].startswith("Keys: Tab/j/k/arrows select | Enter card | Esc back | PgUp/PgDn scroll"))
                    self.assertGreater(frames[0]["bold"], 0)
                    self.assertEqual(frames[2]["bold"], 0)
                    self.assertTrue(any("> ember [working]" in line for line in frames[0]["lines"]))
                    self.assertTrue(any("> fern [blocked]" in line for line in frames[1]["lines"]))
                    card_row = frames[2]["lines"].index("Card")
                    self.assertEqual(frames[2]["lines"][card_row:card_row + 3],
                                     ["Card", "fern [blocked]", "Choose fern fixtures"])
                    self.assertTrue(any("> fern [blocked]" in line for line in frames[3]["lines"]))
                    self.assertTrue(any(color == 1 for row in frames[0]["colors"] for color in row))
                    self.assertTrue(any(color == 2 for row in frames[0]["colors"] for color in row))
                    self.assertIn(b"\x1b[?1049l", log.read_bytes())
                finally:
                    os.close(master)
                    os.close(slave)

    def hook(self, event, data, env=None):
        env = dict(env or self.env, HERDR_PLUGIN_EVENT=event,
                   HERDR_PLUGIN_EVENT_JSON=json.dumps({"event": event.replace(".", "_", 1), "data": data}))
        return subprocess.run([sys.executable, str(PLUGIN / "event-hook.py")], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_hook_contract_and_append(self):
        signal = self.cache / "events.signal"
        signal.write_text('{"seed":true}\n')
        for event, status in (("pane.agent_status_changed", "blocked"), ("pane.closed", None)):
            result = self.hook(event, {"pane_id": "wQ:p2", "agent_status": status})
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        lines = signal.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(json.loads(lines[0]), {"seed": True})
        for line, event, status in zip(lines[1:], ("pane.agent_status_changed", "pane.closed"), ("blocked", None)):
            entry = json.loads(line)
            self.assertEqual(set(entry), {"ts", "event", "pane", "status"})
            self.assertIs(type(entry["ts"]), int)
            self.assertGreater(entry["ts"], 0)
            self.assertEqual((entry["event"], entry["pane"], entry["status"]), (event, "wQ:p2", status))

    def test_hook_null_and_default_cache(self):
        env = dict(self.env, XDG_CACHE_HOME="")
        result = self.hook("pane.closed", {"pane_id": "wQ:p3", "agent_status": "working"}, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "home/.cache/orch/events.signal"
        self.assertEqual(json.loads(path.read_text())["status"], None)
        result = self.hook("pane.agent_status_changed", {"pane_id": "wQ:p3"}, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(path.read_text().splitlines()), 2)

    def test_hook_concurrent_and_short_write(self):
        processes = []
        for n in range(12):
            env = dict(self.env, HERDR_PLUGIN_EVENT="pane.closed",
                       HERDR_PLUGIN_EVENT_JSON=json.dumps({"data": {"pane_id": f"wQ:p{n}"}}))
            processes.append(subprocess.Popen([sys.executable, str(PLUGIN / "event-hook.py")], env=env,
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for process in processes:
            _, err = process.communicate(timeout=10)
            self.assertEqual((process.returncode, err), (0, b""))
        records = [json.loads(line) for line in (self.cache / "events.signal").read_text().splitlines()]
        self.assertEqual(len(records), 12)
        self.assertEqual({entry["pane"] for entry in records}, {f"wQ:p{n}" for n in range(12)})
        spec = importlib.util.spec_from_file_location("event_hook", PLUGIN / "event-hook.py")
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        env = {"HERDR_PLUGIN_EVENT": "pane.closed", "HERDR_PLUGIN_EVENT_JSON": '{"data":{"pane_id":"wQ:p9"}}'}
        with patch.dict(os.environ, env), patch.object(hook.os, "write", return_value=0):
            with self.assertRaisesRegex(OSError, "^short signal write$"):
                hook.main()

    def test_hook_rejects_invalid_event(self):
        signal = self.cache / "events.signal"
        for event, data in (("pane.focused", {"pane_id": "wQ:p2"}),
                            ("pane.closed", {}), ("pane.closed", {"pane_id": 1}),
                            ("pane.agent_status_changed", {"pane_id": "wQ:p2", "agent_status": 3})):
            result = self.hook(event, data)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(signal.exists())

    def test_manifest_and_key_contract(self):
        manifest = tomllib.loads((PLUGIN / "herdr-plugin.toml").read_text())
        self.assertEqual(manifest["id"], "orch")
        self.assertEqual(manifest["platforms"], ["linux", "macos"])
        self.assertEqual(manifest["panes"], [{"id": "board", "title": "Orch board", "placement": "split",
                                           "command": ["python3", "board"]}])
        self.assertEqual(manifest["actions"], [{"id": "board", "title": "Open orch board", "contexts": ["pane"],
                                             "command": ["python3", "board", "--open"]}])
        self.assertEqual(manifest["events"], [{"on": event, "command": ["python3", "event-hook.py"]}
                                             for event in ("pane.agent_status_changed", "pane.closed")])
        key_text = "\n".join(line[2:] for line in (PLUGIN / "herdr-plugin.toml").read_text().splitlines()
                             if line.startswith(("# [[", "# key =", "# type =", "# command =", "# description =")))
        self.assertEqual(tomllib.loads(key_text)["keys"]["command"][0],
                         {"key": "prefix+o", "type": "plugin_action", "command": "orch.board", "description": "Orch board"})

    def test_action_context_and_no_watcher_calls(self):
        fake = self.root / "fake-herdr"
        fake.write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n'
                        'with Path(os.environ["CALLS"]).open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                        'if sys.argv[1:3] == ["pane","current"]: print(json.dumps({"result":{"pane":{"cwd":os.environ["SOURCE"]}}}))\n')
        fake.chmod(0o755)
        repo = self.root / "Moonwell repo"
        repo.mkdir()
        run = repo / ".orch"
        shutil.copytree(FIXTURE, run)
        env = dict(self.env, HERDR_ENV="1", HERDR_BIN_PATH=str(fake), CALLS=str(self.root / "calls"),
                   SOURCE=str(repo), HERDR_PLUGIN_CONTEXT_JSON=json.dumps({"pane_id": "wQ:p1"}))
        result = self.command("--open", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]
        self.assertEqual(calls, [["pane", "current", "--pane", "wQ:p1"],
                                ["plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board",
                                 "--cwd", str(repo), "--env", "ORCH_RUN_DIR=" + str(run)]])
        (self.root / "calls").unlink()
        env["HERDR_PLUGIN_CONTEXT_JSON"] = json.dumps({"cwd": str(repo)})
        result = self.command("--open", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len((self.root / "calls").read_text().splitlines()), 1)
        result = self.command("--open")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "orch board: board action must run inside Herdr\n")
        result = self.command(self.run, "--open")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "orch board: board action must run inside Herdr\n")


if __name__ == "__main__":
    unittest.main()
