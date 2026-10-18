# orch-skill

Source repository for two user-scope agent skills: `orch` (run many coding agents from a
replaceable orchestrator) and `session-close` (the owner's fixed end-of-session routine).
Nothing here is a live install. The installer copies `skills/<name>/` to
`~/.agents/skills/<name>` and links `~/.claude/commands/orch`, which is where every host looks.
Since orch 0.8.0 it also copies orch's four sub-agents (`skills/orch/agents/`) to
`~/.claude/agents/`, never overwriting a different file without `--force-agents`.

## The three systems this repo is part of

Stated by the owner on 2026-10-09:

- **KIS** (`kis-skill`, installed per project under `.agents/skills/kis`) gives a project its
  memory and operating system.
- **orch** (this repo) is the operating system for working with many agents and sub-agents
  across models and TUIs: Claude Code, Codex, Command Code, agy.
- **lore** (`../lore-skill`) is the agents' own memory across projects (lessons, preferences,
  gotchas, profile, references), with a pluggable notes backend; the owner's backend is the
  Tartib space `ai-agents`. It replaced the agent-lessons skill on 2026-10-09; orch and
  session-close call `/lore:load` and `/lore:retro` when it is installed.

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
`windowDurationMins` (300, 10080), reused for five minutes. Command Code:
`usage-cmd.json` written by its statusline, with Claude-shaped rate_limits, preferred while
under five minutes old and before either known window reset. Missing/stale data is unknown
unless the optional `CMD_API_KEY` API fallback supplies a reading. Its cache is
`usage-cmd-api.json`, so it never overwrites the statusline file. `auth.json` is never read.
The insertion block ships at `skills/orch/references/cmd-statusline-cache.sh`. Snapshot age
measures the last statusline write, not necessarily the mod's last upstream fetch. Since orch 0.8.4, choose the CLI by available usage first, from any
orchestrator kind; ask when no candidate is clearly available, and never choose one at or above 80%.

## Live install

`~/.agents/skills/orch` comes from this repo (`bootstrap.sh update --source .`; the installer
removes the retired session-close); `~/.claude/commands/orch` links to the orch commands. The
`designer` sub-agent in `~/.claude/agents/designer.md` points at `references/design.md` and
`scripts/design-pages.py`. The run dir is `<repo>/.orch` only (orch 0.12.1 dropped the legacy
`../<repo>.reports/orch` and `--migrate`); the owner's old runs sit in `<repo>/.orch/run-legacy/`.

## Watcher owners (orch 0.9.0)

One repo run has one watcher. agents.txt may store `agent orch=<owner>`; bare names use
`orchestrator` as their default. Registration writes lock agents.lock and replace agents.txt
atomically. Guarded `move --from <old> --orch <new>` validates every named agent before writing.
Pending events resolve owners at delivery time; wake queues, retries and held notices are
independent per owner. wake.md fallback entries name their owner. Each ledger row has an owner
and each orchestrator exact-matches its own `Next action (<owner>):` line. The watcher uses
an alternate terminal buffer, restores it on exit, redraws changed text only and keeps five
Recent entries.

## Run visibility (orch 0.10.0, ideas from herdr-dagr)

Decided 2026-10-13: borrow dagr's ideas, never its run.json. events.log stays the one append-only
history and the ledger the one memory; the watcher and `check` read the ledger, never write it.
Verdicts are `orch-watch.py mark` lines (tiers, attempts); `add`, `move` and `remove` log
`registered`, `moved` and `removed` (a `move` never resets attempts). The board derives EVID and
Needs you; `check`, `show` and `stats` read the same files. Detail: `skills/orch/references/visibility.md`.
Live Herdr reads go through `scripts/orch-agents.sh` (0.9.1); a guard test keeps raw
`herdr agent list` out of the orchestrator-facing files.

## Agents, test home, machine

- Agents (owner, 2026-10-17): Herdr panes, reused across tasks, each replaced before 200k context.
  `kis-builder` Claude Sonnet 5.5 (effort per task: medium, high for task 4); `kis-reviewer`
  Claude Opus 5.5 (high, read and shell only). Reviewer rule: a different agent on a different
  model; the same host is fine. Picks come from `kis/knowledge/models.md`.
- Test home: `~/.cache/orch-skill-test-home/home` (orch 0.10.0, session-close 1.0.2, lore 1.0.0,
  memory files copied without the hub config, Herdr skill), with the owner's Claude, Codex and
  cmd credential files linked (agy uses the keyring). Live runs: `scripts/measure-live.py run
  --home <test home> --out <dir>`.
- Machine: fresh Linux laptop (2026-10). orch installed here (version: State's Branch line); session-close removed.
  In `~/.agents/skills`, also linked for Claude and agy: lore 1.0.0, herdr (upstream 143bf5f; CLI
  0.9.5) and humanizer 3.1.0. The earlier setup and its `.orch/` proof logs stay on the owner's Mac.
