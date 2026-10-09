<!-- kis:anchor:start -->
## KIS Project Memory

This project uses KIS memory under `kis/`. Knowledge = stable facts. Intent = goals and plans. State = current reality.

- Read `kis/state/` before planning or implementing, then only the Intent and Knowledge the task needs.
- Put each fact in exactly one layer, and update an existing file instead of creating a new one.
- Prove work with real command or verification output before marking anything done.
- Synchronize the KIS layers that changed when work finishes.
- Full instructions: `.agents/skills/kis/SKILL.md`.
- Commands live in `.agents/skills/kis/commands/`: start, plan, act, sync, check, init.
  Claude `/kis:start`, Pi and OpenCode `/kis-start`, Codex `/prompts:kis-start`.
  Antigravity has no custom slash commands: name the step and follow its command file.
<!-- kis:anchor:end -->

# Agent Instructions

This repository is the **source** of the orch and session-close skills. Nothing here is a live
install: `skills/` sits outside every host's discovery path. To use them, install into a home
with `bootstrap.sh`.

## Layout

```text
skills/orch/           the orch package, and what ships
skills/session-close/  the session-close package
docs/research/         research behind orch's design; not installed
tests/                 installer tests, never installed
scripts/               install-skill.sh, run from a source clone only
bootstrap.sh           one-command install, check, update
kis/                   this repo's own project memory (read kis/state first)
```

Installing copies each `skills/<name>/` verbatim to `~/.agents/skills/<name>`. If a file does not
belong in someone's home, it does not belong in `skills/`.

## Rules

- Keep each `SKILL.md` short; it is loaded into context on every use. Detail goes in references.
- `SKILL.md` is instructions at work time; it never documents this repo or the installer.
- Command bodies in `skills/orch/commands/` stand alone (loaded without SKILL.md), so they
  restate rules on purpose. When a command and `SKILL.md` disagree, `SKILL.md` is right.
- `metadata.version` in each SKILL.md is bumped on every change that ships.
- The live install is the owner's working copy of these skills: after a change here, run
  `bootstrap.sh update --source .` and prove it with `check`.

## Checks

```bash
tests/run.sh
```
