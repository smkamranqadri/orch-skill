# orch-skill

Source repository for the **orch** user-scope agent skill: one front door for any repo.
`orch:start` opens a session (project memory first when the repo has `kis/`; many coding agents
in Herdr panes only in Agents mode) and `orch:close` ends it (close agents, sync and check
memory, clean merged worktrees and branches, commit and push as your rules allow). In Agents mode
the run is kept in a ledger on disk with a watcher outside the session, and the orchestrator hands
off at about 150k context instead of compacting.

Nothing here is a live install. The installer copies `skills/orch/` to `~/.agents/skills/orch` and
wires its commands into each host (below). It also copies orch's four sub-agent definitions
(`worker`, `explorer`, `researcher`, `designer`) to `~/.claude/agents/`; a file of yours with the
same name is kept, never overwritten. The old `session-close` skill is retired: install and update
remove its links and its unmodified package, and keep and report anything you changed.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/smkamranqadri/orch-skill/main/bootstrap.sh \
  | bash -s -- install --repo https://github.com/smkamranqadri/orch-skill.git
```

From a local clone: `./bootstrap.sh install --source .`. Flags: `--force` to replace an existing
install (a `.tgz` backup is written to `~/.agents/`; it also replaces a different sub-agent file or Codex/Command Code prompt, keeping a copy there), `--only orch`,
`--no-claude-link` (also skips the sub-agents), `--hosts auto|all|none|codex,cmd,agy` (default `auto`:
the hosts installed here), `--home <dir>` to install somewhere other than `$HOME`.

## Check and update

```bash
./bootstrap.sh check --source .    # exit 0 when the install, the host wiring and the retirement are current
./bootstrap.sh update --source .   # replace the ones that differ, backup kept
```

## Use

| Host | Start | Close | Where the installer puts it |
|---|---|---|---|
| Claude Code | `/orch:start` | `/orch:close` | `~/.claude/commands/orch` (link) |
| Codex | `/prompts:orch-start` | `/prompts:orch-close` | `~/.codex/prompts/orch-<name>.md` (copies) |
| Command Code | `/orch-start` | `/orch-close` | `~/.commandcode/commands/orch-<name>.md` (copies) |
| agy | "run the orch start step" | "run the orch close step" | `~/.gemini/config/skills/orch` (link; agy has no custom slash commands) |

The other commands are `task`, `status`, `event`, `watch` and `handoff`, named the same way. The
method is in `skills/orch/SKILL.md`; every command body is in `~/.agents/skills/orch/commands/`.
Codex and Command Code copies are not links. `bootstrap.sh update` refreshes a copy orch shipped
(recorded in `~/.agents/orch-shipped.tsv`, a backup kept in `~/.agents/`) and removes a shipped copy
whose command was dropped. A file there that orch did not ship is kept and reported; `install --force`
replaces it, keeping a copy. `check` reports all three.

## Development

See `AGENTS.md`. Tests: `tests/run.sh` (they install into a temporary HOME, never yours).
