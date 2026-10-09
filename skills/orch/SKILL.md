---
name: orch
description: "Run a replaceable orchestrator over many agents without letting its own context grow: a run ledger on disk, a watcher in its own pane that wakes the orchestrator when an agent finishes (the orchestrator never blocks), hand off to a fresh orchestrator at about 150k instead of compacting. Use when the user asks you to orchestrate, coordinate or run agents, resume a run, say what is pending or building, or hand off the orchestrator. Works alone; uses KIS, the lessons space and the project's status space when they are present."
metadata:
  version: "0.7.0"
---

# Orchestrator (orch)

Experiment from 2026-10-06. The orchestrator sessions it replaces ran at 300k to 930k context for
most of their turns, held 346 background watchers as children, needed 61 TaskStops, and lost a
next action in one compact. Rules 46 to 51 of `Agents: coordinating parallel agents` in the
lessons space hold the method; this skill is the mechanics. Agents run in Herdr panes
(`herdr` CLI, HERDR_ENV=1). Herdr missing: say so and stop; the user installs it.

Claude Code: `/orch:start`, `/orch:task`, `/orch:status`, `/orch:handoff`, `/orch:watch`, `/orch:event`. Codex and others:
"run the orch start step" and follow `commands/<name>.md`.

## The three rules

1. **Own nothing long-lived, and never block.** Agents run in Herdr panes. The watcher runs in
   its own visible pane via `herdr pane run`. The orchestrator starts no background jobs and does
   not wait: after each step it updates the ledger and ends its turn, so the user can always ask,
   start more agents or give feedback. When an agent finishes, needs the user, or closes, the
   watcher prompts the orchestrator with "orch event: ..." once it is idle with an empty input
   box (`commands/event.md`). Changed 2026-10-07: the foreground `--next` wait of 0.1.0 blocked
   the user for up to nine minutes.
2. **The ledger is the memory.** `<repo>/.orch/ledger.md`, under 60 lines, shape in
   `ledger-template.md`. `scripts/orch-dir.sh` names the dir: it creates `.orch/` and keeps it out
   of git through `.git/info/exclude` (one entry serves every worktree; nothing is committed), and
   it keeps using an old `../<repo>.reports/orch/` while one exists, so a running run is never
   given a second ledger (`--migrate` moves it). Briefs, reports and handoffs live beside it in
   `.orch/<agent>/`. `Next action` is line one and never empty. Update it after every action that
   changes it. A fresh orchestrator orients from it alone. Agent-tool sub-agents die with the
   session, so long builds go in panes and sub-agents do one-message checks.
3. **Read verdicts, not output.** Pane reads `tail -10` at most. Reports and briefs by section
   (`sed -n '/## Result/,$p' | head -40`) or through a cheap sub-agent that returns one line.
   Artifact creation and status-space edits go to a sub-agent. Lessons load once, in start;
   handoff replaces compact, so nothing is reloaded.

## Works alone

Orch needs Herdr and nothing else. Three integrations switch on when present and are skipped
with one line when absent; never ask the user to install them:

| Integration | Present when | Used for | Absent |
|---|---|---|---|
| KIS project memory | `kis/` in the repo | `start` reads `kis/state/current.md`; `task` takes items from `kis/intent/backlog.md`; agents run `/kis:plan` then `/kis:act`; `event` rewrites State after a merge; `handoff` runs the KIS sync and check | the ledger is the whole memory; agents plan in their reply, then act |
| Lessons space (agent-lessons skill, over a notes MCP such as Tartib) | the `lessons:load` command or the skill's notes are reachable | `start` loads preferences, core rules and the coordination note once; pointer prompts say "load the lessons first" | say "no lessons space in this session" once and go on; briefs carry the standing rules themselves |
| Project status space (the user's notes app) | the notes MCP lists a space for the project | one task per feature, a plain thought per move, decisions starred (the user's view) | the ledger's `Done this run` is the only status; mention it when the user asks what moved |

## A run, end to end

When the project has `kis/`, `/kis:start` first; then `/orch:start` (creates the ledger on a
project that has none). `/orch:task <agent> <task>` per task, where the task is a KIS backlog
item, a task in the status space, or the user's words: home (`references/placement.md`), brief
file, worktree, pane, pointer prompt, ledger row, watcher. The agent plans then acts in its worktree; the orchestrator relays
the plan's questions to the user one at a time and records the answers in the ledger. A whole
new module gets a requirements interview first (coordination rule 5). End the turn after each
step; on an "orch event" prompt, verify (coordination rule 35), merge, **close a finished
one-time agent; keep a multi-cycle stream such as design open** (watcher remove, /exit, worktree
and merged branch removed; `commands/event.md` step 3), update the ledger, State when KIS is
present, and the status space when it exists. `/orch:status` whenever the user asks what is
going on. `/orch:handoff` at about 150k. `/session-close` when the day's work ends.

Briefs are files under `.orch/<agent>/brief-<slug>.md`. The prompt is a pointer: "The user asked
for this: <one line>. Your brief is <path>. Read it in full and follow it. Load the lessons first
if the lessons skill is installed. Write your report and handoff to <path> and reply with a short
summary, then continue straight into the plan."

## Commands

| Command | Does |
|---|---|
| `start` | Pick the run dir (`scripts/orch-dir.sh`), orient from the ledger, reconcile with live state, print the board, re-prompt agents stopped by a limit from their resume briefs, then do Next action. Creates the ledger when none exists. |
| `task` | One task (KIS item, status-space task, or the user's words) to one named agent, which plans then acts in its worktree: brief file, worktree and pane if missing, pointer prompt, ledger row, watcher updated, plan questions relayed. |
| `status` | The board in under 20 lines: Next, Waiting on user, Parked, each agent's live state, last five events. |
| `handoff` | At about 150k context, or when asked: retro (if lessons), KIS sync and check (if KIS), status space (if present), ledger and handoff packet, start the successor, confirm it read the ledger, then say "close me". Notice 150k by reading your own pane by id every few prompts: `herdr pane read <your pane id> --source recent-unwrapped --lines 8 \| grep -o 'ctx [^·]*'` (`--current` returns nothing from a tool shell). |
| `watch` | Start the watcher in its own pane, or add agents to the running one; record pane and pid. |
| `event` | Handle the watcher's "orch event" prompt: read each agent's verdict, take the next ledger step, sync State if KIS, reply in five lines, end the turn. |

## Files

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
- `references/brief-rules.md`: the standing rules every brief carries (by pointer with a
  lessons space, in full without one).
- `references/runtimes.md`: one row per agent kind (claude, codex, cmd, agy): how to start and
  prompt it, where its live model shows, default, allowed and avoided models. `task` follows it.
- `scripts/orch-model.sh <agent> [model]`: the kind and model an agent really runs (Herdr's
  list for cmd, pane text for Claude and Codex); exit 1 on a mismatch, 2 when not visible.
  Run it after every `agent start`, before the first prompt.
- `scripts/orch-dir.sh [--check|--migrate] [repo]`: prints the run dir (see rule 2).
- `scripts/orch-usage.py collect|show|line|check <kind>`: each CLI's 5-hour and weekly plan
  usage with reset times (claude from the Claude Code statusline cache, codex from its
  app-server, cmd only with `CMD_API_KEY` set). Report only: the watcher shows it on the
  board, the ledger header carries the line, and `task` asks the user before starting on a CLI
  at or above 80%. Orch never switches CLIs on its own.
- `scripts/orch-watch.py` (`orch-watch.sh` is a wrapper for old ledgers): `watch <dir> [agent...]
  --orch <pane>` runs forever in its pane and draws a plain board; `add`/`remove <dir> <agent>`
  change `<dir>/agents.txt`, which the running watcher rereads; `orch <dir> <pane>` sets whom to
  wake (`<dir>/orchestrator`, rewritten at handoff); `board <dir>` prints the board once;
  `--next <dir> [seconds]` is the old blocking wait, only when the user asks to wait.
- `<dir>/events.log`: one line per change, `<UTC> <agent> <state> | <task title> | ctx <use>`, and
  `<UTC> orchestrator woken | <agents>` per delivered prompt.
- Handoff packets: `<dir>/handoff-<date>-<n>.md`.

## Not yet proved

Proved 2026-10-07 with two Haiku test agents: a turn shorter than one poll is caught (Herdr's
completion counter); a finish while the orchestrator had typed text was held, then delivered
within 30 s of the input clearing. Not yet proved: a Codex orchestrator being woken (its dim
placeholder reads as empty, checked on a live pane), a watcher across a handoff, a long run with
several agents finishing together.
