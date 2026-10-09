# Plan: one watcher, many orchestrators

Approved 2026-10-09 by the owner, answers relayed by orch-3. Standard mode.

## Decisions and scope

- One run and watcher per repo. Agent registrations carry `orch=<target>`; bare registrations
  retain the default in `orchestrator`. Wake batches, retries and held notices are per owner.
- Undelivered events move with their agents to the successor.
- `move <dir> <agent>... --from <old> --orch <new>` refuses agents owned by someone else.
- Ledger rows have an owner; each orchestrator edits only its rows and exact-matches its own
  `Next action (<owner>):` line. Handoff transfers only its own agents.
- Alternate terminal buffer, restored on exit/SIGTERM; redraw only on changed board text;
  last five Recent lines. Board includes owner.
- Update watcher, template and six commands; orch version 0.9.0.
- No usage changes in tasks 1–2 (task 4 adds statusline readings), separate run dirs,
  cross-repo coordination, real installation/restart,
  live watcher files or pane wG:p2. Lore load is read-only; no further snapshots.

## Verification and delivery

Fake Herdr and temporary run dirs, unset HERDR_*; full tests/run.sh output logged and read.
Mutation-check per-owner wake, fallback, recent-five and redraw-on-change (saved originals).
Capture own throwaway pane after several redraws; prove one board and terminal restoration.
Sync this branch's KIS, commit explicit paths on orchwatch only, never push. Handoff at the
brief's specified main-checkout report path. Orchestrator reviews, merges and installs.

## Status

Tasks 1–2 complete on branch, 2026-10-09. Full suite passed (nine shell test files,
eight watcher cases); eight mutation checks killed and original restored. Throwaway Herdr
pane wP:p2 showed one board after 60 redraws, five Recent lines; SIGTERM restored the shell.
Pane closed. Proof logs copied beside the handoff. Receiving orchestrator review pending.

Added by owner while implementing: task 4, cmd statusline usage, in the updated brief.
Read that section after committing tasks 1–2; implement as a separate commit at 0.9.0.

## Task 4: approved extension

Owner requested cmd statusline usage in this same 0.9.0 as its own commit, after tasks 1–2.
Read-only inspected statusline.ts, commandcode/statusline.sh and Claude cache block. Read
usage-cmd.json rate_limits before CMD_API_KEY; expire statusline snapshots at five minutes
(same interval as the watcher usage refresh). Keep API fallback when a key was explicitly set,
with its cache in usage-cmd-api.json so it cannot overwrite the statusline source. Missing or
stale statusline without that fallback is unknown. Update runtime/skill help, temporary cache
fixture tests, fresh/stale and preference mutations. Exact statusline block supplied in handoff and shipped as a tested reference;
never edit ~/.commandcode or ~/.cache.

Task 4 complete on branch, 2026-10-09: seven fixture tests passed; six mutants killed
(fresh/stale boundaries, cache preference, reset/range guards, API cache separation). Exact
statusline block executed with a temporary cache directory, no real home changes. Final suite
passed all ten shell test files, including 15 watcher/cmd unittest cases. Receiving orchestrator
review, merge and live application remain. Cache freshness measures statusline write time; the
installed mod can reuse its last upstream value after a failed fetch.
