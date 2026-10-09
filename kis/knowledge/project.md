# orch-skill

Source repository for two user-scope agent skills: `orch` (run many coding agents from a
replaceable orchestrator) and `session-close` (the owner's fixed end-of-session routine).
Nothing here is a live install. The installer copies `skills/<name>/` to
`~/.agents/skills/<name>` and links `~/.claude/commands/orch`, which is where every host looks.

## The three systems this repo is part of

Stated by the owner on 2026-10-09:

- **KIS** (`kis-skill`, installed per project under `.agents/skills/kis`) gives a project its
  memory and operating system.
- **orch** (this repo) is the operating system for working with many agents and sub-agents
  across models and TUIs: Claude Code, Codex, Command Code, agy.
- **The ai-agents space** in Tartib is the agents' own memory (lessons, preferences, gotchas),
  run by the `agent-lessons` skill. It will get its own repo with a pluggable notes backend
  (not this repo).

Together they are a meta framework; there is no repo for the whole, and orch must work with
or without the other two.

## Layout

```text
skills/orch/           the orch package: SKILL.md, commands/, scripts/orch-watch.py, ledger-template.md
skills/session-close/  the session-close package
docs/research/         the 2026-10-06 research that shaped orch (not installed)
scripts/               install-skill.sh, run from a source clone only
tests/                 installer tests, never installed
bootstrap.sh           one-command install, check and update
kis/                   this repo's own project memory
```

## Stack and constraints

- Bash installer, Ruby for YAML frontmatter (both present on macOS), Python 3 for the watcher.
- Herdr (`herdr` CLI) is the pane and agent runtime orch drives; HERDR_ENV=1 means inside Herdr.
- Each skill carries `metadata.version` in its SKILL.md frontmatter; the installer compares
  per skill. Release tags, when they start, are `v<orch version>`.
- Rules from kis-skill apply: SKILL.md short, detail in references, one owner per fact,
  commands stand alone but SKILL.md wins when they disagree.

## How orch reads plan usage (and its limits)

`skills/orch/scripts/orch-usage.py`. Claude Code: the owner's `~/.claude/statusline-command.sh`
writes the statusline JSON's `rate_limits` to `~/.cache/orch/usage-claude.json` on every
statusline refresh, so the number is as fresh as the last Claude turn on this machine; after a
window reset with no Claude session answering, the board shows the old figure and an ASK that
may not apply (no second source without the OAuth token, which is never read). Codex: the
app-server `account/rateLimits/read` over stdio after `initialize`, windows told apart by
`windowDurationMins` (300, 10080), reused for five minutes. Command Code: only the unofficial
`api.commandcode.ai/alpha/billing/credits` with `CMD_API_KEY` from the environment, unverified;
`auth.json` is never read. Policy is the owner's: report only, ask at 80%, never switch.

## Live install

`~/.agents/skills/orch` and `~/.agents/skills/session-close` come from this repo
(`bootstrap.sh update --source .`); `~/.claude/commands/orch` links to the orch commands. The
`designer` sub-agent in `~/.claude/agents/designer.md` points at `references/design.md` and
`scripts/design-pages.py`. The tartib run (ledger at `../tartib.reports/orch`, Command Code
orchestrator) still uses the legacy layout; `orch-dir.sh --migrate` moves it when the owner says.
