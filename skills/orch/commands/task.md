---
description: Give one task (from KIS, from the status space, or in the user's words) to a named agent, which then plans and acts on it in its own worktree; brief file, worktree and pane if missing, pointer prompt, ledger row, watcher updated.
argument-hint: <agent> <task: KIS backlog item | status-space task id or title | one line of your words> [--kind claude|codex|cmd|agy] [--model <model>] [--place worktree|tab|pane] [--sub explorer|researcher|worker|designer]
---

# Orch: task

One task, one agent. The agent plans, then acts (the KIS loop), in its worktree. The
orchestrator never plans or codes it; it carries questions and decisions between agent and user.

Where it runs is decided first, from `~/.agents/skills/orch/references/placement.md`: a
sub-agent (`--sub <type>`, Claude orchestrators only) for one-message work and small, fully
briefed changes; otherwise a pane agent in a new worktree and workspace (`--place worktree`,
the default), in a new tab on an existing worktree (`--place tab <workspace>`, a second stream
on the same branch that never runs at the same time), or a helper pane (`--place pane`, not an
agent). Say the home in the ledger row.

**Sub-agent route (`--sub`).** Steps 1 to 3 as below (source, brief, usage check for claude),
then: for `worker`, `git worktree add ../<repo>.wt/<slug> -b <slug> main` (no pane); call the
`Agent` tool with that type, in the background, with the same pointer prompt as step 6 plus
"reply with the report, do not wait for anything"; add a row to the ledger's **Sub-agents**
table (name, type, started, report path, status); end the turn. The harness notifies you when
it finishes: verify its report like any other (coordination rule 35), commit from it yourself
when it changed files, remove the worktree, update the row. A read-only type cannot write the
report file: save its reply under `.orch/<agent>/report.md` yourself.

1. Source: find the task. A KIS item (`kis/intent/backlog.md` or a plan file) when the repo has
   `kis/`, a task in the project's status space (`search`, then `get_item`) when the notes MCP
   is present, or the user's words. Quote it in the brief and name where it came from. A
   status-space task gets a thought "assigned to <agent>" now and is marked done on merge
   (preference 33). A whole new module still gets a requirements interview first (coordination
   rule 5); task is for one task.
2. Brief: write `$D/<agent>/brief-<slug>.md` (`D` from `scripts/orch-dir.sh`), one page: the task and its source,
   out of scope, the files or worktree the agent owns, where the design or plan lives, how to
   prove it, where to write report and handoff (`handoff.md` beside the brief), and the standing
   rules from coordination rule 2 (disk, daemons, format only edited files, log files, no git
   checkout or reset in main, no CPU stress). Point at files, paste nothing. Then the loop the
   agent runs. With KIS: "/kis:plan this task; put every question for the user in one message
   and stop; on the answers, /kis:act, prove it, sync your own KIS on your branch (coordination
   rule 38), write the handoff, reply with a short summary." Without KIS: "plan it in one reply
   (scope, files, acceptance checks, questions for the user) and stop; on the answers, build it,
   prove it, write the handoff, reply with a short summary." Without a lessons space, the brief
   also carries the standing rules in full, since the agent cannot load them.
3. Usage: `python3 ~/.agents/skills/orch/scripts/orch-usage.py check <kind>`. Exit 3 means
   that CLI's 5-hour or weekly window is at or above 80% used: show the user
   `orch-usage.py show` and ask, with a recommendation, whether to start here anyway, use
   another kind, or wait for the reset; never switch on your own (owner's rule: report only).
   Exit 2 (unknown) is said in one line and does not block.
4. Home: by `--place`. `worktree` (default), if the agent has no row with a worktree:
   `herdr worktree create --cwd "$PWD" --branch <slug> --base main --path ../<repo>.wt/<slug>
   --label <agent> --no-focus`; keep the workspace and pane ids from the JSON. `tab`: `herdr tab
   create --workspace <ws> --cwd <that worktree> --label <agent> --no-focus`, only when no agent
   is working in that worktree now. `pane`: `herdr pane split <pane> --direction down --ratio
   0.25 --no-focus` and `herdr pane run <id> "<command>"`; no agent, no ledger row beyond a note
   on the stream it serves; stop here.
5. Pane and agent: if the agent is not in `herdr agent list`, start it by its row in
   `~/.agents/skills/orch/references/runtimes.md`: the kind decides the start command, the
   prompt method and the default model (claude: sonnet; codex: gpt-6.1-sol medium; cmd:
   deepseek/deepseek-v4-flash); a model outside the row's Allowed column, or in its Avoid
   column, needs the user's word first. Expect the trust-folder prompt in a new worktree
   (Gotchas: Herdr). Then, before any prompt:
   `~/.agents/skills/orch/scripts/orch-model.sh <agent> <model>`. Exit 1 is a mismatch (wrong
   kind or model came up): exit the agent, start it again with the right flags, check again,
   and say so in the ledger's last event. Exit 2 means the model is not visible: read the last
   ten lines of the pane and decide. Never prompt an agent whose model you have not confirmed:
   a wrong model is cheapest to fix before it has read anything.
6. Prompt: `herdr agent prompt <agent> "The user asked for this: <one line>. Your brief is
   <path>. Read it in full and follow it. Load the lessons first if the lessons skill is
   installed, then continue straight into the plan."` Confirm the status is working (rule 22).
7. Ledger: add or update the row (name, kind/model as `orch-model.sh` reported it, pane,
   worktree and branch, brief, handoff, status working, last event "prompted: plan <slug>").
   Set Next action.
8. Watcher: `python3 ~/.agents/skills/orch/scripts/orch-watch.py add <dir> <agent>` (the running
   watcher picks it up; no restart). No watcher running: `commands/watch.md`.
9. Plan questions: on an "orch event" saying the agent finished with questions, read `tail -15` of
   its pane, ask the user one question at a time with a recommended option (core rule 60),
   record each answer under Open decisions in the ledger with the agent's name, then send all
   answers in one `herdr agent prompt` and confirm it is working again.
10. Reply with the ledger row, one line, and end the turn. Do not wait for the agent: the watcher
   prompts you when it finishes, and the user can keep talking to you meanwhile.
