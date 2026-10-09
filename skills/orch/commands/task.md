---
description: Give one task (from KIS, from Tartib, or in the user's words) to a named agent, which then plans and acts on it in its own worktree; brief file, worktree and pane if missing, pointer prompt, ledger row, watcher updated.
argument-hint: <agent> <task: KIS backlog item | Tartib task id or title | one line of your words> [--model sonnet|opus|haiku] [--kind claude|codex]
---

# Orch: task

One task, one agent. The agent plans, then acts (the KIS loop), in its worktree. The
orchestrator never plans or codes it; it carries questions and decisions between agent and user.

1. Source: find the task. A KIS item (`kis/intent/backlog.md` or a plan file), a Tartib task in
   the project's space (`search`, then `get_item`), or the user's words. Quote it in the brief
   and name where it came from. A Tartib task gets a thought "assigned to <agent>" now and is
   marked done on merge (preference 33). A whole new module still gets a requirements
   interview first (coordination rule 5); task is for one task.
2. Brief: write `../<repo>.reports/<agent>/brief-<slug>.md`, one page: the task and its source,
   out of scope, the files or worktree the agent owns, where the design or plan lives, how to
   prove it, where to write report and handoff (`handoff.md` beside the brief), and the standing
   rules from coordination rule 2 (disk, daemons, format only edited files, log files, no git
   checkout or reset in main, no CPU stress). Point at files, paste nothing. Then the loop the
   agent runs: "/kis:plan this task; put every question for the user in one message and stop;
   on the answers, /kis:act, prove it, sync your own KIS on your branch (coordination rule 38),
   write the handoff, reply with a short summary."
3. Worktree: if the agent has no row with a worktree, `herdr worktree create --cwd "$PWD"
   --branch <slug> --base main --path ../<repo>.wt/<slug> --label <agent> --no-focus`; keep the
   workspace and pane ids from the JSON.
4. Pane and agent: if the agent is not in `herdr agent list`, `herdr agent start <agent> --kind
   <kind> --pane <id> -- --model <model>` (default claude, sonnet; preference 29). Expect the
   trust-folder prompt in a new worktree (Gotchas: Herdr).
5. Prompt: `herdr agent prompt <agent> "The user asked for this: <one line>. Your brief is
   <path>. Read it in full and follow it. Load the lessons first (/lessons:load)."` Confirm the
   status is working (rule 22).
6. Ledger: add or update the row (name, kind/model, pane, worktree and branch, brief, handoff,
   status working, last event "prompted: plan <slug>"). Set Next action.
7. Watcher: `python3 ~/.agents/skills/orch/scripts/orch-watch.py add <dir> <agent>` (the running
   watcher picks it up; no restart). No watcher running: `commands/watch.md`.
8. Plan questions: on an "orch event" saying the agent finished with questions, read `tail -15` of
   its pane, ask the user one question at a time with a recommended option (core rule 60),
   record each answer under Open decisions in the ledger with the agent's name, then send all
   answers in one `herdr agent prompt` and confirm it is working again.
9. Reply with the ledger row, one line, and end the turn. Do not wait for the agent: the watcher
   prompts you when it finishes, and the user can keep talking to you meanwhile.
