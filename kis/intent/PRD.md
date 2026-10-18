# orch v1

Agreed with the owner 2026-10-18.

## In v1

- Registry: project -> orch -> agent, any number of each, across projects.
- Spawn an agent with `--where pane|tab|worktree` (worktree = new git worktree and branch opened
  as its own Herdr workspace).
- Push a `done` or `blocked` notice (blocked = stopped at a permission prompt or question) into
  the owning orch's pane, and only that one.
- Board: a plugin pane showing projects, orchs and agents with live status.
- Hosts: Claude Code and Codex, each as orch and as worker.
- Skill: the plugin API plus a short guide to acting as orch.

## Later

agy and Command Code hosts; orch handoff at a context limit; usage-based host choice; KIS-aware
extras.

## Placement rule

| Agent | Where |
| --- | --- |
| Read-only (explore, research, review) | split pane in orch's tab |
| Read-only, orch's tab already has 3 panes | new tab, same workspace |
| Writes code | worktree workspace |

The skill states this as the default; orch chooses. The plugin enforces one rule: it refuses a
second writer in the same tree.

## Success

Tests cover the registry, routing and the one-writer refusal without Herdr. Live acceptance, in
Herdr:

1. Two repos, a Claude Code orch in one and a Codex orch in the other.
2. Each orch spawns a read-only pane worker and a worktree writer, one worker on each host.
3. Each done notice reaches the right orch only; a worker at a permission prompt shows blocked.
4. The board shows both projects, both orchs and all four agents with live status.
5. A second writer in one tree is refused.
