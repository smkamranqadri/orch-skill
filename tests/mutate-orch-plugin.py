#!/usr/bin/env python3
"""Opt-in literal mutants; each must cause its named test to FAIL, then cmp restores it."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "skills/orch/plugin/board"
HOOK = ROOT / "skills/orch/plugin/event-hook.py"
MANIFEST = ROOT / "skills/orch/plugin/herdr-plugin.toml"
MUTANTS = [
    (HOOK, 'if event not in ("pane.agent_status_changed", "pane.closed"):', 'if False:', 'hook_rejects_invalid_event'),
    (HOOK, 'if not isinstance(pane, str) or not pane:', 'if False:', 'hook_rejects_invalid_event'),
    (HOOK, 'if status is not None and not isinstance(status, str):', 'if False:', 'hook_rejects_invalid_event'),
    (HOOK, 'if event == "pane.closed":', 'if False:', 'hook_null_and_default_cache'),
    (HOOK, 'os.O_WRONLY | os.O_CREAT | os.O_APPEND', 'os.O_WRONLY | os.O_CREAT | os.O_TRUNC', 'hook_contract_and_append'),
    (HOOK, 'if os.write(fd, line) != len(line):', 'if os.write(fd, line) < 0:', 'hook_concurrent_and_short_write'),
    (HOOK, '"ts": int(time.time())', '"ts": str(int(time.time()))', 'hook_contract_and_append'),
    (HOOK, '"status": status', '"status": "none"', 'hook_contract_and_append'),
    (HOOK, 'os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"', 'Path.home() / ".cache"', 'hook_contract_and_append'),
    (HOOK, 'line = (json.dumps(record, separators=(",", ":")) + "\\n").encode()',
           'line = ((json.dumps(record, separators=(",", ":")) + "\\n") * 2).encode()', 'hook_contract_and_append'),
    (BOARD, 'if value.lower().rstrip(".") in ("", "-", "none"):',
            'if value.lower().rstrip(".") in ("", "none"):', 'missing_cache_and_dates'),
    (BOARD, 'if local.date() == now.date():', 'if True:', 'missing_cache_and_dates'),
    (BOARD, 'if section != "pane agents" or not line.lstrip().startswith("|"):',
            'if True:', 'widths_and_rows'),
    (BOARD, 'if len(values) != len(header) or "name" not in header:', 'if False:', 'empty_and_diagnostics'),
    (BOARD, 'if os.environ.get("HERDR_ENV") != "1":', 'if False:', 'live_owner_names_are_read_only_and_optional'),
    (BOARD, 'names.update(live_names or {})', 'names.update({})', 'live_owner_names_are_read_only_and_optional'),
    (BOARD, 'if entry.get("name") and entry.get("pane_id")', 'if True', 'live_owner_names_are_read_only_and_optional'),
    (BOARD, 'if time.monotonic() >= owner_refresh:', 'if True:', 'owner_refresh_uses_one_minute_cache'),
    (BOARD, 'if time.monotonic() >= owner_refresh:', 'if False:', 'owner_refresh_uses_one_minute_cache'),
    (BOARD, 'if owner in names:', 'if False:', 'closed_title_evidence_and_card'),
    (BOARD, 'if re.fullmatch(r"w[^: ]+:p\\S+", owner):', 'if False:', 'registration_owner_wins_and_legacy'),
    (BOARD, 'if not text:\n        warnings.append', 'if False:\n        warnings.append', 'empty_and_diagnostics'),
    (BOARD, 'if bad:\n        warnings.append', 'if False:\n        warnings.append', 'empty_and_diagnostics'),
    (BOARD, 'state not in ("closed", "merged", "gone", "queued")',
            'state not in ("merged", "gone", "queued")', 'closed_title_evidence_and_card'),
    (BOARD, 'state not in ("closed", "merged", "gone", "queued")',
            'state not in ("closed", "merged", "gone")', 'closed_title_evidence_and_card'),
    (BOARD, 'if clean(e["title"]) != "none"', 'if clean(e["title"]) == "none"', 'closed_title_evidence_and_card'),
    (BOARD, 'if clean(e["ctx"]) != "none"', 'if clean(e["ctx"]) == "none"', 'closed_title_evidence_and_card'),
    (BOARD, 'if mark:\n            evidence', 'if False:\n            evidence', 'closed_title_evidence_and_card'),
    (BOARD, 'owners.get(name) or row.get("owner")', 'row.get("owner")', 'registration_owner_wins_and_legacy'),
    (BOARD, 'if t["state"] not in ("closed", "gone")', 'if True', 'cache_and_needs'),
    (BOARD, 'ready = [t for t in pending if set(t["depends"]) <= done]',
            'ready = list(pending)', 'graph_order_cycles_and_selection'),
    (BOARD, 'if not ready:\n            yield pending', 'if not ready:\n            yield []', 'graph_order_cycles_and_selection'),
    (BOARD, 'if path:\n        return Path(path).expanduser().resolve()', 'if False:\n        return Path(path).expanduser().resolve()', 'explicit_titles_and_run_override'),
    (BOARD, 'if not pane:\n                raise ValueError', 'if False:\n                raise ValueError', 'explicit_titles_and_run_override'),
    (BOARD, 'title = clean(row.get("title") or row.get("task"))', 'title = "none"', 'explicit_titles_and_run_override'),
    (BOARD, 'columns = max(1, width // 39)', 'columns = 1', 'widths_and_rows'),
    (BOARD, 'if edges:\n                add', 'if False:\n                add', 'widths_and_rows'),
    (BOARD, 'if selected == task["name"]:\n                        heading',
            'if False:\n                        heading', 'graph_order_cycles_and_selection'),
    (BOARD, 'if event_day != day:', 'if False:', 'widths_and_rows'),
    (BOARD, 'body, footer = lines[:-1], lines[-1]', 'body, footer = lines, ("", [])', 'curses_terminal_transitions'),
    (BOARD, 'attr |= curses.A_BOLD', 'attr |= 0', 'curses_terminal_transitions'),
    (BOARD, 'if key in (27, curses.KEY_BACKSPACE):', 'if False:', 'curses_terminal_transitions'),
    (BOARD, 'elif key in (10, 13, curses.KEY_ENTER) and selected:', 'elif False:', 'curses_terminal_transitions'),
    (BOARD, 'if args.open and os.environ.get("HERDR_ENV") != "1":', 'if False:', 'action_context_and_no_watcher_calls'),
    (BOARD, 'directory = Path(directory)\n    now',
            'directory = Path(directory)\n    (directory / "watcher.pid").write_text("0\\n")\n    now', 'plain_readonly_and_repeat'),
    (MANIFEST, 'on = "pane.closed"', 'on = "pane.focused"', 'manifest_and_key_contract'),
]


def main():
    with tempfile.TemporaryDirectory(prefix="orch-plugin-mutants-") as scratch:
        saved = {}
        for n, (path, old, new, test) in enumerate(MUTANTS, 1):
            if path not in saved:
                saved[path] = Path(scratch) / path.name
                shutil.copyfile(path, saved[path])
            original = saved[path].read_text()
            assert original.count(old) == 1, (path, old)
            try:
                path.write_text(original.replace(old, new))
                result = subprocess.run([str(ROOT / "tests/test-orch-plugin.sh"), "PluginTests.test_" + test],
                                        cwd=ROOT, capture_output=True, text=True, timeout=30)
                log = result.stdout + result.stderr
                if result.returncode == 0 or f"FAIL: test_{test} " not in log:
                    print(log, flush=True)
                    raise AssertionError(f"mutant {n}: named FAIL not observed: {test}")
                print(f"{n:02d} killed: {path.name}: {test}", flush=True)
            finally:
                shutil.copyfile(saved[path], path)
                subprocess.run(["cmp", "-s", str(saved[path]), str(path)], check=True)
        print(f"{len(MUTANTS)} mutants killed; every restore cmp-identical", flush=True)


if __name__ == "__main__":
    main()
