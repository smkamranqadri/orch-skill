# Runtimes: one row per agent kind

Orch drives agents through Herdr panes. Each kind starts, is prompted and reports its model
differently, and the owner's model policy (preference 29 and its 2026-10-09 refinement) differs
per kind. `task` picks the row from `--kind`, and `scripts/orch-model.sh <agent> <model>` reads
the live model back after start; a mismatch is fixed before the first prompt.

Any orchestrator kind starts any agent kind: Claude Code can start Codex or Command Code, Codex
can start Claude Code or Command Code, and Command Code can start either (owner, 2026-10-09).
Which one runs a task is decided by usage first (`commands/task.md` step 3), then by the row's
model for the task.

| Kind | Start in a shell pane | Prompt | Live model | Default model | Allowed | Avoid | Orchestrator | Sub-agent route |
|---|---|---|---|---|---|---|---|---|
| `claude` (Claude Code) | `herdr agent start <name> --kind claude --pane <id> -- --model <m>` | `herdr agent prompt` works | pane text ("Sonnet 5.5"); not in `agent list` | `sonnet` for code; `opus` for new design and hard bugs; `haiku` for read-only checks, exploring, small tasks, and as a trial for edits and fixes | opus, sonnet, haiku | nothing beyond the usage rule below | yes | yes (`Agent` tool: worker, explorer, researcher, designer) |
| `codex` (Codex CLI) | `herdr agent start <name> --kind codex --pane <id> -- -m gpt-6.1-sol -c 'model_reasoning_effort="medium"'` | `herdr agent prompt` works | pane text ("GPT-6.1-Sol medium") | `gpt-6.1-sol` medium | gpt-6.1-sol | `gpt-6-astra` (eats the usage) | yes (waking by the watcher not yet proved) | no |
| `cmd` (Command Code) | no Herdr kind: `herdr pane send-text <pane> "cmd -t -n <name> -m <model>"`, `herdr pane send-keys <pane> enter`, then `herdr agent rename <pane> <name>`; expect language and "learn taste" dialogs on first start | `agent prompt` is refused ("not an active named agent"): `pane send-text` plus `send-keys enter`; the watcher writes wakes to `wake.md` instead | `tokens.model` in `herdr agent list` ("deepseek/deepseek-v4-flash"); before the first turn, pane text without the provider prefix | `deepseek/deepseek-v4-flash` for code, read-only checks and exploring | `deepseek/deepseek-v4-pro` for hard bugs and long reasoning; `xiaomi/mimo-v2.6-pro` for design and vision (screenshots, exports); trial: `deepseek/deepseek-v4.1-flash`; any other only as a trial the owner names | every Claude model offered by cmd, and gpt-6-astra; on the GOAT plan also anything under about 300 requests per 5 hours (Grok 4.x, GLM-5.2 Fast, GLM-5.3, Kimi K3, Kimi K2.7 Code HighSpeed, Qwen 3.8 Max, MiMo V2.6 Pro UltraSpeed) and the free or stealth models | yes (observed, not driven: the owner presses Enter) | no |
| `agy` | `herdr agent start <name> --kind agy --pane <id> -- --model <m>`; stops at "trust this folder" in a new worktree | `herdr agent prompt` works | pane text; pattern unverified | none set; send one tiny prompt first (its quota ran out on first use once) | as the owner names | nothing recorded | untried | no |

Rules that apply to every kind:

- Name the kind and the model in the brief and in the ledger row (`kind/model`), then run
  `orch-model.sh <agent> <model>` before the first prompt. Exit 1 is a mismatch: stop the agent
  (`/exit` through the kind's prompt method), start it again with the right flags, check again.
  Exit 2 means the model is not visible: read the last ten lines of the pane yourself.
- Never pass `--permission-mode auto` to `agent start`; start in default mode, the owner switches.
- A Claude agent in a new worktree stops at the trust prompt; `agent start` then returns
  `agent_not_ready`. Codex may self-update and exit on first start; look at the pane and start
  again. Both from `Gotchas: Herdr`.
- Context use is pane text for every kind: `herdr agent read <name> --source recent-unwrapped
  --lines 8 | grep -o 'ctx [^·]*'` (Claude); Codex and cmd show their own counters.
- Plan usage (5-hour and weekly windows) is read per CLI by `scripts/orch-usage.py`: claude
  from the statusline cache, codex from its app-server, cmd only with `CMD_API_KEY`. The watcher
  shows it on the board. `task` chooses the kind by usage first: a kind with usage available for
  the task, never one at or above 80%, and the user is asked when that is not clear.

Command Code models were chosen on 2026-10-09 from the GOAT plan's per-model budget
(https://commandcode.ai/docs/plans/goat): the plan's windows are in dollars, so a model's
requests per 5 hours decides what it costs (deepseek-v4-flash about 30,800, mimo-v2.6-pro about
5,700, deepseek-v4-pro about 1,980, Claude Sonnet about 238). The vendor's figures are averages;
an agent turn makes many requests.
