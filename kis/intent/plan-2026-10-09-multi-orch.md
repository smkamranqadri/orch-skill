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
- No usage changes, separate run dirs, cross-repo coordination, real installation/restart,
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
