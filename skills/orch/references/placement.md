# Placement: where a piece of work runs

Three homes, decided before any agent starts. The question is always the same: who must see it,
how long it runs, and whose files it touches.

| Work | Home | Why |
|---|---|---|
| A one-message answer: a read-only check, a search of the code, research with sources, a report read and reduced to one line, an Artifact or status-space edit, a memory tidy with an exact fact list | **Sub-agent** (`Agent` tool: `explorer`, `researcher`, `worker`, `designer`; Claude orchestrators only) | Returns one message, so nothing is polled; costs no pane. It dies with the orchestrator, so nothing that must outlive a handoff. |
| A small change with a complete brief that nobody needs to watch: one or two files, proof named in the brief, under about twenty minutes | **Sub-agent `worker`** started with the `Agent` tool's `isolation: "worktree"`, so its working directory is its own worktree, never main's checkout; it reports the worktree path and branch, and the orchestrator verifies and commits from there | Same as above; the isolated worktree keeps it off main (coordination rule 14) without trusting the brief for it. Past twenty minutes or past one or two files, it is a pane agent. |
| Anything that changes product code on its own branch; anything long; anything the user wants to watch or talk to; any kind other than Claude (codex, cmd, agy); any multi-cycle stream (design rounds, build with review loops) | **Pane agent, new worktree in a new Herdr workspace**: `herdr worktree create --cwd "$PWD" --branch <slug> --base main --path ../<repo>.wt/<slug> --label <agent> --no-focus`, then `agent start` in the pane it returns | One worktree and branch per stream, split by file ownership (rule 14). Visible, resumable, survives the orchestrator. |
| A second stream on the **same branch** that must not run at the same time as the first: review after build, verification, a docs pass over the same files, a resume of a stopped agent while its pane stays readable | **Same worktree, new tab** in that workspace: `herdr tab create --workspace <ws> --cwd <worktree> --label <agent> --no-focus`, then `agent start` | Shares the files, so the two never run together; the first stream's pane stays readable for the user. |
| A helper that the agent and the user watch beside the work: a dev server, a test watcher, a log tail, the orch watcher itself | **New pane in the same tab**: `herdr pane split <pane> --direction down --ratio 0.25 --no-focus`, then `herdr pane run <id> "<command>"` | Not an agent; belongs next to what it serves. Never started with `&` in the orchestrator's shell. |
| Replacing an agent past about 200k context with a fresh one from its handoff | Same worktree: `/exit` in its pane, then `agent start` there; or a new tab when the old pane must stay readable | Keeps the branch and the files; coordination rule 27 and thought 395 (a long build that would re-read 200k in minutes finishes in place). |
| The orchestrator's successor at handoff | New pane in the orchestrator's own workspace, visible: `herdr pane split --current --direction right --no-focus` | Preference 28: the user can read and interrupt it. |

Rules that go with the table:

- Never run two implementing agents in one working tree at the same time, whatever the home.
- A sub-agent gets the same pointer-style brief as a pane agent (a file, one line of prompt),
  because its report must be as checkable. Read-only sub-agents reply with the report; the
  orchestrator saves it under `.orch/<agent>/`.
- A sub-agent's row goes in the ledger's **Sub-agents** table with its start time and report
  path; `handoff` lists any still running as lost (rule 50). A pane agent's row goes in **Pane
  agents** with workspace, tab and pane ids, so a successor can find it.
- When the kind is not Claude, the sub-agent route does not exist: everything is a pane agent.
- When in doubt between sub-agent and pane: if the user might want to talk to it, pane.
