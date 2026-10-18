# Orch model matrix (shipped default)

What each model is good for and what it costs, so orch can propose an agent's harness, model and
effort with a reason. This is the generic default. orch reads the user's own matrix,
`~/.agents/orch/models.md`, when it exists; `scripts/orch-models.py rebuild` (the `models`
command) builds it from the CLIs installed on that machine and keeps the user's notes. Nothing
here was measured on the reader's machine: the Measured column is for the user's own runs.

Prices are API list prices per 1M tokens (input / cached input / output), with the page each was
read from and the date; the plan the user pays through changes the bill, not the ranking. Efforts
raise cost through extra thinking tokens, billed as output: start at medium and raise it only
where the task has unknowns. Reviewer rules: code review is a different agent on a different
model (the same host is fine); plan review is a different CLI than the author's.

## Plans

- none recorded

## Matrix

| Host | Model | Efforts | Price in / cached / out | Price source | Priced | Good for | Measured | Seen |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5 | low, medium, high, xhigh, max | 4 / 0.2 / 20 | platform.claude.com/docs/en/about-claude/pricing | 2026-10-17 | design, hard debugging, reviewing another model's work |  | - |
| claude | claude-sonnet-5-5 | low, medium, high, xhigh, max | 2 / 0.1 / 10 | platform.claude.com/docs/en/about-claude/pricing | 2026-10-17 | building from a clear brief, research, reviewing a smaller model's work |  | - |
| claude | claude-haiku-5-5 | low, medium, high, xhigh, max | 0.1 / 0.01 / 0.5 | platform.claude.com/docs/en/about-claude/pricing | 2026-10-17 | lookups, mechanical edits, log scans |  | - |
| claude | claude-fable-5-1 | low, medium, high, xhigh, max | 10 / 0.25 / 50 | platform.claude.com/docs/en/about-claude/pricing | 2026-10-17 | the hardest long-horizon reasoning only |  | - |
| codex | gpt-6-astra | low, medium, high, xhigh, max, ultra | 10 / 1 / 50 | developers.openai.com/api/docs/pricing | 2026-10-17 | rarely worth its price on a small plan |  | - |
| codex | gpt-6.1-sol | low, medium, high, xhigh, max, ultra | 2 / 0.1 / 10 | developers.openai.com/api/docs/pricing | 2026-10-17 | building and review; a different model family from Claude |  | - |
| codex | gpt-6-luna | low, medium, high, xhigh, max | 0.1 / 0.01 / 0.5 | developers.openai.com/api/docs/pricing | 2026-10-17 | high-volume simple work |  | - |
| codex | gpt-5.6-terra | low, medium, high, xhigh, max, ultra | 2 / 0.2 / 12 | developers.openai.com/api/docs/pricing | 2026-10-17 | nothing gpt-6.1-sol does not do as well for less |  | - |
| agy | gemini-3.8-flash | low, medium, high | 0.75 / 0.075 / 3.75 | ai.google.dev/gemini-api/docs/pricing | 2026-10-17 | quick agentic work |  | - |
| agy | gpt-oss-120b | medium | 0.15 / 0.075 / 0.6 | openrouter.ai/api/v1/models | 2026-10-17 | cheap extra runs; shallow reviews |  | - |
| cmd | z-ai/glm-5.3-flash | - | 0.15 / 0.03 / 0.5 | openrouter.ai/api/v1/models | 2026-10-17 | cheap bulk work |  | - |
| cmd | deepseek/deepseek-v4-flash | - | 0.091 / 0.018 / 0.182 | openrouter.ai/api/v1/models | 2026-10-17 | the cheapest capable option |  | - |
| cmd | qwen/qwen3.8-max-0902 | - | 2 / 0.25 / 6 | openrouter.ai/api/v1/models | 2026-10-17 | a stronger open model when a third opinion is needed |  | - |

## Picks by job

| Job | First choice | Alternatives |
|---|---|---|
| plan-review | claude/claude-opus-5-5 high | codex/gpt-6.1-sol high; claude/claude-sonnet-5-5 high |
| build | claude/claude-sonnet-5-5 medium | codex/gpt-6.1-sol medium |
| code-review | claude/claude-opus-5-5 high | codex/gpt-6.1-sol high; claude/claude-sonnet-5-5 high |
| research | claude/claude-sonnet-5-5 medium | codex/gpt-6.1-sol medium |
| bulk | codex/gpt-6-luna low | claude/claude-haiku-5-5 low; cmd/deepseek/deepseek-v4-flash |

## Pick rules

`plan-review` needs `--author <cli>`: the first candidate on a different CLI wins. `code-review` needs `--builder <host/model>`: the first candidate on a different model wins. Other jobs take the first candidate. A candidate missing from the Matrix, or with an effort its row does not list, is skipped. Edit the picks table by hand; a rebuild keeps it.

## Sources

- ai.google.dev/gemini-api/docs/pricing
- developers.openai.com/api/docs/pricing
- openrouter.ai/api/v1/models
- platform.claude.com/docs/en/about-claude/pricing
