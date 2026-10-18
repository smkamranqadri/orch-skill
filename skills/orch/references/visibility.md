# Visibility: marks, the Needs-you block, check, show, stats

The watcher and these commands derive everything from two files: `events.log` (the one
append-only history) and the ledger (read, never written by them). The orchestrator spends one
short command per verdict. No other state file exists.

`ORCH=python3 ~/.agents/skills/orch/scripts/orch-watch.py`; `<dir>` is the run dir.

## Marks

`$ORCH mark <dir> <agent> <tier> "<what>" [--proof <path>]` appends
`<UTC> <agent> mark:<tier> a<n> | <what> | proof <path or ->`. `what` is plain words; a ` | ` in it
becomes ` / `. A mark never changes the agent's live state or the board's SINCE.

| Tier | Say it when | `what` |
|---|---|---|
| `reported` | the agent says it is done and you have not checked | its one-line result |
| `verified` | you re-ran the proof yourself (`--proof` names the log) | what passed, with counts |
| `asserted` | no proof is possible | why not |
| `sent-back` | the proof failed and you re-prompt the agent; opens attempt n+1 | the cause |
| `merged` | its work is merged | the commit |
| `open` | kept on purpose for a next cycle | `next cycle: <what>` |
| `closed` | pane, watcher entry and worktree are gone | the merge commit |
| `handoff` | you hand the run on; the agent field is your pane id | `ctx <n>` |

Attempt n is 1 plus the sent-back marks since the agent's last `registered` line. `add` logs
`registered orch=<owner>` (only for a newly added name), `move` logs `moved orch=<new>` (so a
handoff keeps the count), `remove` logs `removed`. Marks on a name that is not registered (an
owner pane) are allowed.

## The board

EVID is the latest mark of the agent's current life: `◆ verified`, `◇ reported`, `! asserted`,
`↩ a2` (sent back, attempt 2), `⇢ merged`, `✓ closed`, `○ open`, blank before any mark. Recent
shows marks as "web-ids verified: suite 399 pass".

NEEDS YOU sits above the table, is omitted when empty, shows five lines and "+n more", oldest
first. It lists:

1. a blocked agent;
2. an agent finished (done, or idle after working or blocked) with no mark after that finish,
   for 10 minutes or more;
3. the latest mark is `reported` for 10 minutes or more;
4. the latest mark is `verified` or `merged` for 30 minutes or more (a later `open` or `closed`
   mark ends it);
5. wakes held for an owner (busy, typing, or not found);
6. the ledger's `Waiting on user:` line when it is not "none";
7. a usage ASK.

Times come from events.log, so a restarted watcher shows the same block.

## check

`$ORCH check <dir> [--owner <pane>] [--offline]`: one line per finding, `<owner>: [rule] text`.
`--owner` keeps that owner's findings plus the run-wide ones (ledger length, watcher, log). Exit 0
clean, 1 findings, 3 when the ledger, a table row or agents.txt cannot be parsed (it never
guesses). `--offline` skips the owner-pane liveness check.

| Rule | Finding |
|---|---|
| `ledger-length` | the ledger is over 60 lines |
| `next-action` | a registered owner has no `Next action (<owner>):` line, or it is empty |
| `plan-review` | a `Ledger: minimal` ledger names a written `Plan:` but its `Plan review:` lacks `outcome: ready` (minimal ledgers are checked for this, `ledger-length` and `next-action` only; they have no watcher) |
| `no-row` | a registered agent has no row in Pane agents |
| `row-unregistered` | a row not `closed`, `gone` or `queued: after <task>` whose agent is not registered |
| `not-closed` | the row says done/merged/verified, or the latest mark is verified/merged, and it is neither `closed` nor `open: next cycle` |
| `watcher` | agents are registered and `<dir>/watcher.pid` is missing or its pid is dead (an old ledger's `## Watcher` section is ignored) |
| `owner-dead` | an owner pane is not live |
| `log` | events.log has lines outside its grammar (hand-written lines, a date without a time zone), counted with the first example |

The status cell of a Pane agents row starts with one fixed word (`working`, `done`, `merged`,
`closed`, `gone`, `open: next cycle <what>`) so `check` can read it.

## show and stats

`$ORCH show <dir> <agent>`: the ledger row, owner, live state, model and context, the brief and
handoff paths marked `[present]` or `[missing]`, the attempts with their causes, the evidence,
and the last events, in 15 lines at most.

`$ORCH stats <dir> [agent]`: per agent the working time, finishes, attempts, the mean
finish-to-wake and finish-to-first-mark delays (with how many finishes had one) and closed or not;
run totals and the context at each `handoff` mark. These are the exit numbers of the replaceable
orchestrator experiment except the orchestrator's maximum context between
handoffs, which events.log cannot hold.
