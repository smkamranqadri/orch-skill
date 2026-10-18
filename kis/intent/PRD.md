# orch v1

Agreed with the owner 2026-10-18. Build plan: `kis/intent/plan-2026-10-18-orch-v1.md`.

## In v1

- Registry: project -> orch -> agent, any number of each, across projects.
- Spawn an agent with `--where pane|tab|worktree` (worktree = new git worktree and branch opened
  as its own Herdr workspace).
- Push a `done` or `blocked` notice (blocked = stopped at a permission prompt or question) into
  the owning orch's pane, and only that one, and only while that orch is idle or done.
- Board: a plugin pane showing projects, orchs and agents with live status; opens on register.
- Hosts: Claude Code and Codex, each as orch and as worker.
- Reuse: each agent has a role (plan, build, review, explore); orch re-prompts an idle agent of
  the needed role and spawns only when there is none. Test runs need no agent.
- Skill: the plugin API, the five commands below, and the matrix.

## Commands

Each `orch:` command is the delegated twin of a `kis:` command: `kis:*` runs directly in the
current agent, `orch:*` runs it through orch and its agents.

| Command | Does |
| --- | --- |
| `orch:start` | No KIS: install it (KIS's curl installer) and run `kis:init`, no decline path. Then `kis:start`; register as orch; adopt orphaned agents of the project; open the board; report status and suggest the next task. |
| `orch:plan` | `kis:plan` run by a planner agent picked from the matrix; the user answers it in its pane; on its notice orch has the plan reviewed by an agent on a different CLI. |
| `orch:act` | `kis:act` with workers: per task, propose a spawn from the matrix, wait for "go", brief, wait for the notice, review by an agent on a different model, verify proof, merge, close. Orch never writes product code. |
| `orch:close` | Close finished agents, `kis:sync`, `/lore:retro` if lore is installed, list merged branches and worktrees and ask before removing each, deregister. |
| `orch:model` | Draft the matrix from research (prices, plans, measurements) and the user's answers; write it only on approval. |

Before any spawn orch shows one line per agent (name, host, model, effort, where, writes, matrix
row) and waits; one "go" approves the batch. `confirm = false` in `~/.config/orch/config.toml`
turns this off; it is v1's only setting.

## Matrix

`~/.config/orch/matrix.md`, user-level: one table, Job -> Host, Model, Effort, Where,
Alternative, plus a rules line. Research inputs are not stored in it. With no matrix, orch
proposes from its own judgment and says so; `orch:start` never creates one.

## Placement rule

| Agent | Where |
| --- | --- |
| Read-only (explore, research, review, plan) | split pane in orch's tab |
| Read-only, orch's tab already has 3 panes | new tab, same workspace |
| Writes code | worktree workspace |

The skill states this as the default; orch chooses. The plugin enforces one rule: it refuses a
second writer in the same tree.

## Later

agy and Command Code hosts; orch handoff at a context limit; usage-based host choice; merge
helpers; board input beyond `q`.

## Success

Tests cover the registry, routing and the one-writer refusal without Herdr. Live acceptance, in
Herdr:

1. Two repos, a Claude Code orch in one and a Codex orch in the other.
2. Each orch spawns a read-only pane worker and a worktree writer, one worker on each host.
3. Each done notice reaches the right orch only; a worker at a permission prompt shows blocked.
4. The board shows both projects, both orchs and all four agents with live status.
5. A second writer in one tree is refused.
