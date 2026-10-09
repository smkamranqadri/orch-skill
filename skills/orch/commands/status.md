---
description: Print the orchestrator board from the ledger and live agent state in under 20 lines.
argument-hint: [optional ledger dir]
---

# Orch: status

Owner is your orchestrator pane id. One run and watcher serve all owners. Edit only rows
owned by you and exact-match `Next action (<owner>):` when updating it; preserve every other
owner's line. Legacy rows without an owner fall back to `<dir>/orchestrator`; claim them only
when that default is you: pin them with `move <dir> <agent>... --from <your pane id>
--orch <your pane id>` and record the owner in their ledger rows.

Answer "what is pending, what is building, are the agents working" from one file and one command.

1. `D=$(~/.agents/skills/orch/scripts/orch-dir.sh --check 2>/dev/null)` unless given; then
   read the ledger header and every `Next action (<owner>):` line, Waiting on user and Parked.
   Do not assume a fixed header length when several owners share the run.
2. `python3 ~/.agents/skills/orch/scripts/orch-watch.py board <dir>`: the usage line, each
   agent's live state, since when, owner, context use and task, and the last five events. When the
   user asks about usage or limits, add `orch-usage.py show` (one line per CLI with reset times
   and the ASK warnings).
3. Print those two blocks as the board and nothing else. Do not read panes, reports or KIS.
   If a row's live status differs from the ledger, fix only your owned ledger row and say so in one line.
