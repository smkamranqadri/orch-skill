---
description: Print the orchestrator board from the ledger and live agent state in under 20 lines.
argument-hint: [optional ledger dir]
---

# Orch: status

Answer "what is pending, what is building, are the agents working" from one file and one command.

1. `sed -n '1,8p' <dir>/ledger.md` (header, Next action, Waiting on user, Parked).
2. `python3 ~/.agents/skills/orch/scripts/orch-watch.py board <dir>`: each agent's live state,
   since when, context use and task, and the last eight events.
3. Print those two blocks as the board and nothing else. Do not read panes, reports or KIS.
   If a row's live status differs from the ledger, fix the ledger row and say so in one line.
