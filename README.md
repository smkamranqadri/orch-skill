# orch-skill

Source repository for two user-scope agent skills:

- **orch**: run many coding agents (Claude Code, Codex, Command Code, agy, in Herdr panes) from a
  replaceable orchestrator: a run ledger on disk, a watcher outside the session, hand off at
  about 150k context instead of compacting.
- **session-close**: the fixed end-of-session routine (project memory sync and check, close
  agents, update the project's Tartib space, retrospective, commit and push).

Nothing here is a live install. The installer copies `skills/<name>/` to `~/.agents/skills/<name>`
and links `~/.claude/commands/orch`, which is where Claude Code, Codex and other hosts look.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/orch-skill/main/bootstrap.sh \
  | bash -s -- install --repo https://github.com/OWNER/orch-skill.git
```

From a local clone: `./bootstrap.sh install --source .`. Flags: `--force` to replace an existing
install (a `.tgz` backup is written to `~/.agents/`), `--only orch` or `--only session-close`,
`--no-claude-link`, `--home <dir>` to install somewhere other than `$HOME`.

## Check and update

```bash
./bootstrap.sh check --source .    # exit 0 when every installed skill equals the source
./bootstrap.sh update --source .   # replace the ones that differ, backup kept
```

## Use

Claude Code: `/orch:start`, `/orch:task`, `/orch:status`, `/orch:event`, `/orch:watch`,
`/orch:handoff`, `/session-close`. Codex and others: "run the orch start step" and follow
`~/.agents/skills/orch/commands/<name>.md`. The method is in `skills/orch/SKILL.md`.

## Development

See `AGENTS.md`. Tests: `tests/run.sh` (they install into a temporary HOME, never yours).
