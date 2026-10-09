---
description: Orient a fresh orchestrator from the run ledger, reconcile with live state, print the board, re-prompt agents stopped by a limit, then do the Next action.
argument-hint: [optional ledger dir; default from scripts/orch-dir.sh]
---

# Orch: start (also resume)

Full method: `~/.agents/skills/orch/SKILL.md`. Act without asking; the ledger holds the decisions.

1. Load lore once, if the lore skill is installed (`/lore:load`, or its notes
   over the notes MCP): `Agents: preferences`, `Agents: core rules`, `Agents: coordinating
   parallel agents`. No gotchas notes; agents load their own. Not installed: say "no lore
   in this session" once and go on.
2. Run dir: `$ARGUMENTS`, or `D=$(~/.agents/skills/orch/scripts/orch-dir.sh)` from the repo
   root. It creates `.orch/` (excluded from git) or, while an old `../<repo>.reports/orch/`
   run exists, names that one and creates nothing; migrate only when the user asks
   (`orch-dir.sh --migrate`). Then read the ledger `$D/ledger.md`, and `kis/state/current.md`
   (head 60) when the repo has `kis/` (no `kis/`: one line, "no KIS in this repo").
   No ledger: copy `~/.agents/skills/orch/ledger-template.md` there, fill it from State (if
   any) and `herdr agent list`, and set Next action from State's Next. No State or no Next: set
   Next action to "ask the user for the first assignment", print the board, and ask in one
   line; then `/orch:task` does the rest.
3. Reconcile: `herdr agent list` and `git worktree list` against the ledger rows. Fix the rows;
   a ledger row with no live agent is "gone", a live agent with no row gets one.
4. Check the watcher: `kill -0 $(cat <dir>/watcher.pid)`. Dead or missing: run `commands/watch.md`.
   Alive and not started by a handoff: point it at yourself,
   `python3 ~/.agents/skills/orch/scripts/orch-watch.py orch <dir> <your pane id>`.
5. Print the board (`commands/status.md`).
6. For every agent whose status is stopped by a limit or gone with a resume brief, re-prompt it
   from that brief: "The user asked for this: resume. Your brief is <handoff or resume brief>.
   Read it in full and continue." Record the prompt as its last event.
7. Do the Next action. Then update the ledger, including the new Next action, and end the turn;
   the watcher prompts you on the next event.

Started by a handoff: stop after step 5, reply with the board and the Next action, and act only
on "go". Until then two orchestrators are live and only the old one may act.
