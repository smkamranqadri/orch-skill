# Plan: run visibility (ideas adapted from herdr-dagr)

Drafted 2026-10-13 from a read of github.com/aemrebarut/herdr-dagr (v0.3.1). The owner chose
not to try dagr itself, and to adapt what fits ("let's adapt what we can and improve our workflow
and visibility"), scope "all five". Standard mode. Approved 2026-10-13 by the owner
("This session" orchestrates: orch-5, wG:p6; ctx-trims "Verify, then merge", done as 0.9.1 be5bf15).

## Why (evidence from this repo's and the tartib run, 2026-10-13)

- Done but never closed: 5 agents here (lorecheck, orchfix, tartib-search, lore-ids, ctx-trims),
  4 in the tartib run. The live board still lists three finished 2026-10-09.
- Tartib run: 15 of 19 `done` lines never reached the orchestrator. One wait was about 9.8 h.
- Ledger drift: 75 lines (limit 60). It says "agents: none" while agents.txt holds three.
  Handoff packets carried facts the ledger lacked, and one contradicted it.
- The orchestrator's verdicts were hand-written into events.log in six free-form lines
  ("2026-10-09 22:01 tartib-search done; suite re-run 399 passed") that the board cannot parse.
  Re-prompts and send-backs are only prose in the ledger.

## Design rules

- The model spends almost nothing: the watcher derives and renders. The orchestrator runs at most
  one short command per verdict. The ledger stays the run's memory, and events.log stays the
  one append-only history (no run.json, no second state file).
- Read-only toward the ledger: the watcher and `check` parse it but never write it.
- Not adopted from dagr: the DAG drawing, folding, the in-pane message composer (it conflicts with
  the idle-and-empty wake rule and the cmd wake.md path), and interactive keys.

## Scope (orch 0.10.0)

1. **`mark`**: `orch-watch.py mark <dir> <agent> <tier> "<what>" [--proof <path>]`. Tiers:
   `reported` (the agent says done), `verified` (the orchestrator re-ran the proof),
   `asserted` (no proof possible, say why), `sent-back` (opens attempt n+1; what = the cause),
   `merged`, `open` (kept on purpose for a next cycle; what = "next cycle: <what>"; it holds
   the not-closed rules off until the agent's next state change), `closed`, and `handoff` (the
   agent field is the owner pane, what = "ctx <n>"; marks on unregistered names are allowed).
   Appends `<UTC> <agent> mark:<tier> a<n> | <what> | proof <path or ->` to events.log.
   `add` also appends `<UTC> <agent> registered orch=<owner>`, `move` appends `moved orch=<new>`
   (never `registered`, so a handoff keeps the attempt count), and `remove` appends `removed`.
   Attempt n is 1 plus the sent-back marks since the agent's last `registered` line.
   Marks never change the watcher's live state. The board's SINCE uses state lines only.
2. **Board**: an `EVID` column (`◆ verified`, `◇ reported`, `! asserted`, `↩ a2`, `⇢ merged`,
   blank before any mark). A **Needs you** block sits above the table and is omitted when empty,
   at most 5 lines plus "+n more", oldest first:
   blocked agents; finished with no mark after 10 min; `reported` and not verified after 10 min;
   `verified` or `merged` and neither `closed` nor `open` after 30 min; wakes held per owner; the ledger's
   `Waiting on user:` line when not "none"; and usage ASK.
   Recent shows marks in plain words ("lore-ids verified: suite 399 pass").
3. **`check <dir>`**: lint, one line per finding, exit 0 clean, 1 findings, 3 when it cannot
   parse (never guess). Each finding names its owner. `--owner <pane>` shows only that
   owner's findings plus the run-wide rules (line count, watcher, log). Rules:
   - the ledger is over 60 lines;
   - a registered owner has no `Next action (<owner>):` line, or the line is empty;
   - a registered agent has no ledger row, or a row that is not `closed`/`gone` is not
     registered (names that only carry marks, such as owner panes, are exempt);
   - a row or mark is done/verified/merged but neither `closed` nor "open: next cycle";
   - the ledger's Watcher line pid is not alive, or its agents differ from agents.txt;
   - an owner pane is not live (skipped with `--offline`);
   - events.log has unparseable lines (counted, with the first example).
4. **`show <dir> <agent>`**: one card of at most 15 lines. Ledger row fields, owner, live state,
   model and ctx, brief and handoff paths each marked present or missing, attempts with
   their causes, evidence, and the agent's last 8 events.
5. **`stats <dir> [agent]`**: per agent from events.log: working time, finishes, attempts
   (rework), finish→wake delay, finish→first-mark delay (the orchestrator's verify latency),
   closed or not. Run totals add handoff ctx from `handoff` marks. These are rule 51's exit
   numbers, except max orchestrator context between handoffs, which events.log cannot hold.
6. **Commands** (each restates its step, since commands stand alone):
   - `event`: step 2 marks `reported`, `verified`, `asserted` or `sent-back` per verdict.
     Step 3's close marks `merged`/`closed` and runs `check` before ending the turn.
   - `start`: runs `check` after the board and fixes owned findings first.
   - `status`: adds `check`'s count when non-zero.
   - `task`: a re-prompt to redo work marks `sent-back` with the cause.
   - `handoff`: `check` must be clean for own rows, then a `handoff` mark with own ctx.
   SKILL.md gains one Files entry per command, and the detail goes in a new
   `references/visibility.md` (tiers, Needs-you rules, check rules).
   Ledger template: no new columns (evidence lives in events.log). The status cell starts with
   one fixed word (`working`, `done`, `merged`, `closed`, `gone`, or `open: next cycle <what>`) so
   `check` can parse it, and the template states the 60-line limit.
   Version 0.10.0.

## Order and dependencies

0. **Done 2026-10-13 (merged be5bf15, orch 0.9.1).** ctx-trims (worktree `../orch-skill.wt/ctx-trims`, owner w3:pZ, "done, awaiting
   user") holds uncommitted edits to SKILL.md, ledger-template.md, start/task/watch.md,
   runtimes.md, plus orch-agents.sh and two tests. The owner decides merge or drop before this
   starts. This plan builds on the result.
1. mark + registered/removed lines + parser (everything else reads them).
2. Board EVID column and the Needs you block.
3. check. 4. show. 5. stats. 6. commands, reference, SKILL.md, version.

## Verification and delivery

- Fake Herdr and temporary run dirs. Unset HERDR_* and the session's pane variables.
  Write the full `tests/run.sh` output to a log and read it.
- Unittest cases per scope item, with fixtures built from the real event lines quoted above
  (including the six hand-written ones, which `check` must count).
- Mutation-check, restoring each saved original, with `__pycache__` deleted and
  PYTHONDONTWRITEBYTECODE=1: attempt counting (including `move` keeping it), `open` holding
  off the not-closed rule, `--owner` filtering, each Needs-you rule and its time boundary,
  marks not moving SINCE, each check rule, and stats' finish→mark delay.
- Render the board in a throwaway pane at 80 and 150 columns and look at it, with Needs you
  both empty and full.
- Builder: a Sonnet pane agent on its own branch, through `/orch:task`. Commit explicit paths on
  that branch only, never push. The orchestrator verifies in a clean detached checkout, merges,
  runs `bootstrap.sh update --source .` and `check`, and restarts the live watcher only when
  `herdr agent list` shows no agent working under it.

## Acceptance

- The fixture of today's run makes `check` report the three done-not-closed agents, 75 > 60,
  the "agents: none" mismatch and six unparseable lines.
- A `sent-back` then `verified` sequence shows `↩ a2` and then `◆ verified`. `show` lists both
  attempts with the cause.
- Needs you lists an agent finished for 11 minutes with no mark, and not one finished for
  9 minutes.
- `stats` prints finish→mark delay from fixture times that are checked by hand against the
  log lines.
- Not proved by this plan: a real multi-agent run using marks end to end (first live run after
  install).

## Status

**Done 2026-10-14:** merged to main (ff to ab56aae) by orch-5 after a clean detached suite
(13 files) and three more mutants killed; installed live (0.10.0, `check` exit 0); the live
watcher restarted on it and draws the EVID column and mark lines (pane wG:p2). Not pushed. Still
not proved: a real multi-agent run using marks end to end. Follow-up: a watcher restart resets
finish ages, so old finishes reach Needs you 10 minutes after a restart. The builder's notes below
are kept as history.

Built 2026-10-13 on branch `visibility` (code through eae8358, orch 0.10.0), one commit per scope
item: mark 450020a, board eae952e, check bc258e6, show 4f5639c, stats a3230a6, commands, reference
and version 7908567, then 087f34a (mutation survivors) and eae8358 (clip the Waiting line). Not
merged, not installed, not pushed. Proved by the builder: the full suite in a clean detached
checkout at eae8358 (all twelve files pass), 50 mutants killed with the original written back,
the board rendered in a throwaway pane at 80 and 150 columns with Needs you empty and full.

Measured against the plan's numbers, today's fixture (`tests/fixtures/visibility`, copies of the
real 2026-10-13 run) gives: ledger 79 lines (the plan said 75), three done-not-closed agents,
the "agents: none" mismatch, and seven events.log lines outside the grammar (the plan said six:
four hand-written dateless lines plus three ISO-stamped free-form "closed/merged" lines). Choices
the plan left open: a `sent-back` mark is written as the attempt it opens (`a2`); `add` of an
already registered name logs nothing; Needs you reads events.log timestamps with an injectable
`--now`; `check` exits 3 only when the ledger, a table row or agents.txt cannot be parsed
(stray log lines are findings); `verified` does not require `--proof`.

Not proved: a real multi-agent run using marks end to end (first live run after install), and the
live watcher drawing the new board (only `board` was rendered).
