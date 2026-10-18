---
description: Rebuild the user's model matrix from the installed CLIs, their plans and current prices; keep their notes. Also shows it and picks an agent from it.
argument-hint: [rebuild | show | pick <job>]
---

# Orch: models

M = `python3 ~/.agents/skills/orch/scripts/orch-models.py`. The user's matrix is
`~/.agents/orch/models.md`, outside the package, so an orch update never replaces it. Orch reads
it when it proposes an agent and falls back to the shipped `references/models.md`
(`M path` says which). Never read the whole file: use `M show [--host H]` and `M pick`.

## Proposing an agent

`M pick <job>` (jobs: `plan-review`, `build`, `code-review`, `research`, `bulk`) prints
`<harness> <model> <effort>`. Propose that to the user with a reason and wait for approval; never
start an agent on a pick unapproved. The reviewer rules are enforced by the helper:

- `code-review` needs `--builder <host/model>`: a different agent on a different model; the same
  host is fine. `M pick code-review --builder claude/claude-sonnet-5-5 --reviewer <host/model>`
  checks a reviewer the user named; exit 1 `REFUSED` means choose another.
- `plan-review` needs `--author <cli>`: the reviewer is a different CLI than the author's.

Exit 1 with no candidate: say so and ask the user; do not invent a model.

## Rebuild (`rebuild`, or when the user asks to refresh models or prices)

1. Which plans: ask the user once which plan they have on each installed CLI (Claude, Codex, agy,
   cmd). Keep the answers for `--plan claude=NAME --plan codex=NAME ...`; plans already in the
   matrix need no question.
2. Claude's model ids: the CLI does not list them. Fetch the models page
   (platform.claude.com/docs/en/about-claude/models), write one id per line to a temp file, pass it as
   `--claude-models <file>`.
3. Prices: for every row of `M discover`'s models, read the provider's pricing page
   (Claude: platform.claude.com/docs/en/about-claude/pricing; Codex: developers.openai.com/api/docs/pricing;
   Google: ai.google.dev/gemini-api/docs/pricing; open models on cmd: commandcode.ai/pricing or
   openrouter.ai/api/v1/models). Write a temp file `{"sources_failed": [{"source": "...", "reason":
   "..."}], "prices": [{"host": "codex", "model": "gpt-6.1-sol", "in": 2, "cached": 0.1, "out": 10,
   "source": "developers.openai.com/api/docs/pricing", "date": "YYYY-MM-DD"}]}`. A price needs the
   page it came from; a page that did not load goes in `sources_failed`. Never fill a price from
   memory or a neighbouring model.
4. `M rebuild --plan ... --claude-models <file> --prices <file>`. It discovers Codex from
   `~/.codex/models_cache.json`, cmd from `cmd --list-models`, agy from `agy models` (agy takes
   `<model>-<effort>`), merges into the user's matrix and keeps their `Good for` and `Measured`
   cells, picks, free sections and plans.
5. Report its output as is: exit 0 clean; exit 3 means lines to relay: `UNREACHABLE` (a CLI that
   failed), `PRICE SOURCE UNREACHABLE`, `NO PRICE SOURCE`, `PLAN UNKNOWN`, `PROBLEM`. Say which
   were not reached and stop there; a missing price stays `unknown` until a source is read.
   `not installed` is informational. Models gone from a CLI stay in the file, listed as not
   discovered; remove them by hand only if the user asks.

Measured notes are the user's: record what a model did on this machine in its `Measured` cell by
editing the row, never in a rebuild input. Change picks by editing the Picks table.
