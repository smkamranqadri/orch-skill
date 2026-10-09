---
name: orch
description: "Run a replaceable orchestrator over many agents without letting its own context grow: a run ledger on disk, a watcher in its own pane that wakes the orchestrator when an agent finishes (the orchestrator never blocks), hand off to a fresh orchestrator at about 150k instead of compacting. Use when the user asks you to orchestrate, coordinate or run agents, resume a run, say what is pending or building, or hand off the orchestrator. Pairs with the agent-lessons coordination note and session-close."
metadata:
  version: "0.2.0"
---

# Orchestrator (orch)

Experiment from 2026-10-06. The orchestrator sessions it replaces ran at 300k to 930k context for
most of their turns, held 346 background watchers as children, needed 61 TaskStops, and lost a
next action in one compact. Rules 46 to 51 of `Agents: coordinating parallel agents` in Tartib
hold the method; this skill is the mechanics.

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
2. **The ledger is the memory.** `../<repo>.reports/orch/ledger.md`, next to the briefs, outside
   git, under 60 lines, shape in `ledger-template.md`. `Next action` is line one and never empty.
   Update it after every action that changes it. A fresh orchestrator orients from it alone.
   Agent-tool sub-agents die with the session, so long builds go in panes and sub-agents do
   one-message checks. The project's Tartib space stays the user's feature view (preference 33).
3. **Read verdicts, not output.** Pane reads `tail -10` at most. Reports and briefs by section
   (`sed -n '/## Result/,$p' | head -40`) or through a Haiku sub-agent that returns one line.
   Artifact creation and Tartib edits go to a sub-agent. Lessons load once, in start; handoff
   replaces compact, so nothing is reloaded.

## A run, end to end

`/kis:start` for the project, then `/orch:start` (creates the ledger on a project that has none).
`/orch:task <agent> <task>` per task, where the task is a KIS backlog item, a Tartib task, or the
user's words: brief file, worktree, pane, pointer prompt, ledger row, watcher. The agent runs
plan then act in its worktree; the orchestrator relays the plan's questions to the user one at a
time and records the answers in the ledger. A whole new module gets a requirements interview
first (coordination rule 5). End the turn after each step; on an "orch event" prompt, verify
(coordination rule 35), merge, **close a finished one-time agent; keep a multi-cycle stream such as design open** (watcher remove, /exit, worktree and merged branch removed; `commands/event.md` step 3), update the ledger and the project's Tartib space. `/orch:status` whenever the user asks what is going
on. `/orch:handoff` at about 150k. `/session-close` when the day's work ends.

Briefs are files under `../<repo>.reports/<stream>/brief-<name>.md`. The prompt is a pointer:
"The user asked for this: <one line>. Your brief is <path>. Read it in full and follow it. Load the
lessons first. Write your report and handoff to <path> and reply with a short summary."

## Commands

| Command | Does |
|---|---|
| `start` | Orient from the ledger, reconcile with live state, print the board, re-prompt agents stopped by a limit from their resume briefs, then do Next action. Creates the ledger when none exists. |
| `task` | One task (KIS item, Tartib task, or the user's words) to one named agent, which plans then acts in its worktree: brief file, worktree and pane if missing, pointer prompt, ledger row, watcher updated, plan questions relayed. |
| `status` | The board in under 20 lines: Next, Waiting on user, Parked, each agent's live state, last five events. |
| `handoff` | At about 150k context, or when asked: retro, KIS sync and check, Tartib, ledger and handoff packet, start the successor, confirm it read the ledger, then say "close me". Notice 150k by reading your own pane every few prompts: `herdr pane read --current --source recent-unwrapped --lines 8 \| grep -o 'ctx [^·]*'`, the way rule 27 reads other agents. |
| `watch` | Start the watcher in its own pane, or add agents to the running one; record pane and pid. |
| `event` | Handle the watcher's "orch event" prompt: read each agent's verdict, take the next ledger step, reply in five lines, end the turn. |

## Files

- `ledger-template.md`: the ledger's shape. Copy it on the first start.
- `scripts/orch-watch.py` (`orch-watch.sh` is a wrapper for old ledgers): `watch <dir> [agent...]
  --orch <pane>` runs forever in its pane and draws a plain board; `add`/`remove <dir> <agent>`
  change `<dir>/agents.txt`, which the running watcher rereads; `orch <dir> <pane>` sets whom to
  wake (`<dir>/orchestrator`, rewritten at handoff); `board <dir>` prints the board once;
  `--next <dir> [seconds]` is the old blocking wait, only when the user asks to wait.
- `<dir>/events.log`: one line per change, `<UTC> <agent> <state> | <task title> | ctx <use>`, and
  `<UTC> orchestrator woken | <agents>` per delivered prompt.
- Handoff packets: `../<repo>.reports/orch/handoff-<date>-<n>.md`.

## Not yet proved

Proved 2026-10-07 with two Haiku test agents: a turn shorter than one poll is caught (Herdr's
completion counter); a finish while the orchestrator had typed text was held, then delivered
within 30 s of the input clearing. Not yet proved: a Codex orchestrator being woken (its dim
placeholder reads as empty, checked on a live pane), a watcher across a handoff, a long run with
several agents finishing together.
