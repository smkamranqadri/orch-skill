# Models: what each can do and what it costs

Probed 2026-10-17 on the owner's Linux laptop. Prices are API list prices per 1M tokens (input /
cached input / output), from the provider pages named at the end; the owner pays through plans, so
they rank relative cost, not the bill. "Measured" means seen on this machine on 2026-10-17
(`kis/knowledge/start-cost.md`, the phase 1 reviews). Capability tiers are the coordinator's
judgment from that use, not benchmarks: no comparable public scores exist for these versions.

## Matrix

| Host (plan) | Model | Price in / cached / out | Good for | Measured here | Effort |
|---|---|---|---|---|---|
| Claude Code (Max) | Opus 5.5 | 4 / 0.20 / 20 | design, hard debugging, review of Sonnet's work | found real defects with reproductions | high for review and design |
| Claude Code (Max) | Sonnet 5.5 | 2 / 0.10 / 10 | building from a clear brief, research, review of Haiku or Luna work | built phase 1 tasks 1-3; defects came from gaps in the brief; ~110k tokens per start + fix session | medium; high when the task has many unknowns |
| Claude Code (Max) | Haiku 5.5 | 0.10 / 0.01 / 0.50 | lookups, mechanical edits, log scans | not used yet | low |
| Claude Code (Max) | Fable 5.1 | 10 / 0.25 / 50 | hardest long-horizon reasoning only | not used | high |
| Codex (ChatGPT Plus, $20) | gpt-6-astra | 10 / 1.00 / 50 | rarely worth it on Plus: 5-45 messages per 5 hours | not used; was the Codex default until 2026-10-17 | medium |
| Codex (Plus) | gpt-6.1-sol | 2 / 0.10 / 10 | building and review, a different model from Claude | two thorough plan reviews; the 5-hour window ran out after 8 baseline sessions and a few reviews (15-160 messages per 5 hours) | medium to build, high to review |
| Codex (Plus) | gpt-6-luna | 0.10 / 0.01 / 0.50 | high-volume simple work: 350-3,000 messages per 5 hours | not used | low or medium |
| Codex (Plus) | gpt-5.6-terra | 2 / 0.20 / 12 | nothing gpt-6.1-sol does not do as well for less | not used | |
| agy (Google AI plan) | Gemini 3.8 Flash (High) | 0.75 / 0.075 / 3.75 | quick agentic work | weekly quota ran out after ~8 sessions; took 17-75 steps per session | its default |
| agy | gpt-oss-120b (Medium) | 0.15 / 0.075 / 0.60 | cheap extra runs (now agy's default) | finished every baseline case at a third of Flash's tokens; reviews were shallow, with wrong claims | medium |
| cmd (credits at model cost) | glm-5.3-flash | 0.15 / 0.03 / 0.50 | cheap bulk work | finished every baseline case, at 2-9x Claude's tokens per session | its default |
| cmd | deepseek-v4-flash | 0.091 / 0.018 / 0.182 | cheapest capable option | not used | |
| cmd | qwen3.8-max-0902 | 2.00 / 0.25 / 6.00 | a stronger open model when a third opinion is needed | not used | |

cmd also offers Claude, OpenAI and Gemini models at API cost, which is dearer than the same models
through the Max and Plus plans.

## Picks by job

| Job | First choice | Alternative |
|---|---|---|
| Plan or design review | Opus 5.5 high, if Claude did not write it; else Codex gpt-6.1-sol high | Sonnet 5.5 high |
| Build from a brief | Sonnet 5.5 medium (high for many unknowns) | Codex gpt-6.1-sol medium |
| Code review | a different model from the builder: Opus 5.5 high for Sonnet's work, Sonnet 5.5 high for Luna's | Codex gpt-6.1-sol high |
| Research and web lookups | Sonnet 5.5 medium | Codex gpt-6.1-sol medium |
| Mechanical or bulk work | Codex gpt-6-luna low | Haiku 5.5 low, cmd deepseek-v4-flash |

Owner, 2026-10-17: the Codex default model is gpt-6.1-sol (`~/.codex/config.toml`, was
gpt-6-astra); Luna, not Haiku, is the first choice for bulk work; the rest stands until revisited.

Rules behind the picks (owner, 2026-10-17): a reviewer is a different agent on a different model;
the same host is fine. Effort raises cost through extra thinking tokens, which are billed as output,
so start at medium and raise it only where the task has unknowns.

## Gaps

Not published: how Max counts Opus against Sonnet; Antigravity's per-model quotas; official Google
AI plan prices (third-party: Pro $19.99, Ultra $99.99 and $199.99).

Sources: platform.claude.com/docs/en/about-claude/pricing,
developers.openai.com/api/docs/pricing, learn.chatgpt.com/docs/pricing,
ai.google.dev/gemini-api/docs/pricing (updated 2026-10-16), openrouter.ai/api/v1/models,
commandcode.ai/pricing, antigravity.google/pricing, support.claude.com (Max plan article).
