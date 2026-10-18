# Agents mode: files and scripts

Loaded in Agents mode only; `SKILL.md` points here.

- `agents/`: the four named sub-agents (`worker`, `explorer`, `researcher`, `designer`) that
  `placement.md` and `task --sub` use; the installer copies them to `~/.claude/agents/`.
- `ledger-template.md`: the ledger's shape. Copy it on the first start.
- `references/placement.md`: where work runs: sub-agent (one-message work, small fully briefed
  changes; Claude only), pane agent in a new worktree and workspace (anything on its own branch,
  anything long, other kinds), a new tab on the same worktree (a second stream on the same
  branch, never at the same time), a helper pane (servers, watchers). `task` decides from it.
- `references/design.md`: the design stream. With pen.dev: Pencil frames, exports, three JSON
  files, then `scripts/design-pages.py` builds the round's local `review.html` (changed screens,
  before and after, the user's feedback above each, review-first list) and `prototype.html`
  (every frame, clickable regions, the whole app at once). Without pen.dev: ask the user to
  install it or to skip the design step; nothing else is invented.
- `references/brief-rules.md`: the standing rules every brief carries (carried in full by every brief).
- `references/runtimes.md`: one row per agent kind (claude, codex, cmd, agy): how to start and
  prompt it, where its live model shows, default, allowed and avoided models. `task` follows it.
- `scripts/orch-model.sh <agent> [model]`: the kind and model an agent really runs (Herdr's
  list for cmd, pane text for Claude and Codex); exit 1 on a mismatch, 2 when not visible.
  Run it after every `agent start`, before the first prompt.
- `scripts/orch-agents.sh [--panes] [--fields a,b,...] [<name-or-pane>]`: the compact live
  agents (`name,pane,status,model,cwd`) and panes (`pane,label,cwd,agent`), one row each, sorted
  by the first field. Read this instead of the full Herdr agent or pane list JSON: it is about
  12.6k chars a call. A named target exits 2 when it is not live.
- `scripts/orch-dir.sh [--check] [repo]`: prints the run dir (see SKILL.md, the ledger rule).
- `scripts/orch-usage.py collect|show|line|check <kind>`: each CLI's 5-hour and weekly plan
  usage with reset times (claude from the Claude Code statusline cache, codex from its
  app-server, cmd from its statusline cache while under five minutes old, with optional
  `CMD_API_KEY` fallback). Usage decides the kind first: `task` starts the
  agent on a CLI with usage available for the task, never on one at or above 80%, and asks the
  user when no candidate is clearly available. `board` and the board plugin show usage from the
  cache, and the ledger header carries the line.
- `scripts/orch-watch.py`: one watcher per repo run, headless; it sleeps on the plugin's
  `events.signal` file (Herdr events) and re-reads Herdr's agent list on every wake and every 60 s.
  `add <dir> <agent>... --orch <owner>` registers agents; bare lines fall back to
  `<dir>/orchestrator`. `move <dir> <agent>... --from <old> --orch <new>` transfers only
  the named owner's agents; pending events follow them. Each owner gets its own wake batch
  and retry timer, so a busy owner does not hold another's events. `orch <dir> <pane>` changes
  only the legacy default; never use it for multi-owner handoff. `remove` stops watching named
  agents. `board <dir>` prints the board once, with the usage line from the cache (the watcher
  never refreshes usage; `orch-usage.py check <kind>` and the board plugin do). The pid lives in
  `<dir>/watcher.pid`; the ledger has no Watcher section.
- `orch-watch.py mark <dir> <agent> <tier> "<what>" [--proof <path>]`: record a verdict (tiers
  `reported verified asserted sent-back merged open closed handoff`). The board's EVID column and
  its NEEDS YOU block read the marks; `event` marks every verdict and `task` marks a send-back.
- `orch-watch.py check <dir> [--owner <pane>] [--offline]`: lint the run, one line per finding
  with its owner; exit 0 clean, 1 findings, 3 when the ledger cannot be parsed. `start`, `event`,
  `status` and `handoff` run it. It never writes the ledger. A `Ledger: minimal` ledger is checked
  for length, Next action and the plan review only, with no watcher. A row `queued: after <task>`
  needs no registration.
- `orch-watch.py show <dir> <agent>` (one card) and `orch-watch.py stats <dir> [agent]` (timings
  from events.log): see `references/visibility.md`.
- `references/visibility.md`: the mark tiers, the Needs-you rules and the check rules.
- `<dir>/events.log`: one line per change, `<UTC> <agent> <state> | <task title> | ctx <use>`,
  `<UTC> orchestrator woken | <agents>` per delivered prompt, `<UTC> <agent> mark:<tier> a<n> | <what>
  | proof <path or ->` per verdict, and `registered`, `moved`, `removed` per registration change.
- Handoff packets: `<dir>/handoff-<date>-<n>.md`.

## Not yet proved

Proved 2026-10-07 with two Haiku test agents: a turn shorter than one poll is caught (Herdr's
completion counter); a finish while the orchestrator had typed text was held, then delivered
within 30 s of the input clearing. Not yet proved: a Codex orchestrator being woken (its dim
placeholder reads as empty, checked on a live pane), a watcher across a handoff, a long run with
several agents finishing together.
