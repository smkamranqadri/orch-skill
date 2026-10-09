---
description: Start or restart the watcher in its own Herdr pane for the named agents and record it in the ledger.
argument-hint: <agent> [agent...]
---

# Orch: watch

Owner is your orchestrator pane id. One run and watcher serve all owners. Edit only rows
owned by you and exact-match `Next action (<owner>):` when updating it; preserve every other
owner's line. Legacy rows without an owner fall back to `<dir>/orchestrator`; claim them only
when that default is you: pin them with `move <dir> <agent>... --from <your pane id>
--orch <your pane id>` and record the owner in their ledger rows.

The watcher lives in a visible pane, not in this session, so closing the orchestrator never
strands it and the user can read it. One watcher per run; it reads `<dir>/agents.txt` on every
poll, so adding an agent never needs a restart.

W = `python3 ~/.agents/skills/orch/scripts/orch-watch.py`; `<dir>` is the run dir from
`scripts/orch-dir.sh` (the ledger's folder).

1. Already running (`kill -0 $(cat <dir>/watcher.pid)` succeeds): `W add <dir> $ARGUMENTS --orch <your pane id>`
   (`herdr pane current --current`, field `pane_id`). Keep existing owners and the default. Done; skip to 5.
2. Get or make a shell pane in this workspace, labelled `watcher`:
   `herdr pane split --current --direction down --ratio 0.25 --no-focus` returns the pane id;
   `herdr pane rename <id> watcher`.
3. `herdr pane run <id> "W watch <dir> $ARGUMENTS --orch <your pane id>"`.
   Never start it with `&`, `nohup` or a background job in your own shell: the user would not
   see it, and it would die with you. If a sandbox refuses the herdr command, ask the user to
   approve it; there is no fallback.
4. After 10 seconds: `herdr pane list` shows the `watcher` pane, `<dir>/events.log` has a
   "watcher start" line and one line per agent, and `herdr pane read <id> --source visible`
   shows the board.
5. Record pane id, pid and agent names under Watcher in the ledger.

The pane redraws only when board text changes, including the minute clock, in an alternate
terminal buffer. Exit and SIGTERM restore the terminal and cursor. The pane shows a board: each agent's state (working, finished, idle, needs you, closed), since
when, its owner, context use and task title, then the last five events in plain words.

When an agent finishes, needs the user, or closes, the watcher shows a Herdr notification and
queues an "orch event" for that agent's owner. Each owner has its own batch, retry timer
and held notice; one busy or typing owner does not hold another's events. It sends each batch
once its owner is idle and its input box is empty (dim placeholder text is ignored), so it never
types over the user. A queue held over two minutes raises a notification.

The orchestrator never waits for the watcher. It ends its turn after each step and the watcher
prompts it (`commands/event.md`). `W --next <dir> 540` still exists for a one-off wait, but it
blocks the user; use it only when the user asks to wait.
