---
name: orch
description: "Front door for any repo, on any host. With kis/ it runs KIS's start step and adds one mode, Agents; without kis/ it installs KIS or keeps a minimal ledger. Agents mode runs a replaceable orchestrator over many agents without letting its own context grow: a run ledger on disk, a watcher in its own Herdr pane that wakes the orchestrator when an agent finishes (it never blocks), hand off to a fresh orchestrator at about 150k instead of compacting. Use when the user starts a session, asks you to orchestrate, coordinate or run agents, resume a run, say what is pending or building, or hand off the orchestrator."
metadata:
  version: "0.11.0"
---

# Orchestrator (orch)

Experiment from 2026-10-06. The orchestrator sessions it replaces ran at 300k to 930k context for
most of their turns, held 346 background watchers as children, needed 61 TaskStops, and lost a
next action in one compact. This skill is the mechanics of the method.

Claude Code: `/orch:start`, `/orch:task`, `/orch:status`, `/orch:handoff`, `/orch:watch`,
`/orch:event`, `/orch:close`. Codex and others: "run the orch start step" and follow
`commands/<name>.md`.

## Modes

`start` is the front door. It loads nothing beyond itself until a mode is chosen.

| Repo | Start does | Modes |
|---|---|---|
| has `kis/` | version check (below), then KIS's start step and its single confirmation | KIS's Fast, Standard, Phase, plus **Agents** |
| no `kis/` | offers to install KIS once, else the minimal ledger | one session, no agents; Agents on request |

Herdr (`herdr` CLI, HERDR_ENV=1) is required in Agents mode only; missing: say so and stop that
mode, the user installs it. The ledger, watcher, Herdr and brief references load in Agents mode
only. Outside it the whole footprint is `commands/start.md` and, with no KIS, the minimal ledger.

**KIS version.** `scripts/orch-kis-version.sh` reads the repo's vendored KIS: 0.11.0 or newer
follows a `Run:` pointer; below that, `start` offers the repo's one-line update and continues if
declined. Declined: an Agents run keeps its record in the ledger only and writes nothing into
State ("pointer off").

**Minimal ledger** (no KIS, no agents): `ledger-minimal-template.md` holds Task, Next action,
Plan and Plan review, Decisions, Done; no pane, owner or watcher fields. `orch-watch.py check`
accepts it without a watcher. A written plan is reviewed before implementation (reviewer a
different CLI than the author; harness, model and effort proposed to the user); the ledger
records `Plan review: <reviewer>; outcome: ready|rework; <date>`, and `check` reports
`[plan-review]` until it says `ready`; `start` does not implement while it does.

## State contract (Agents mode in a KIS >= 0.11 repo, not "pointer off")

Every orch step that writes `kis/state/current.md` (`start`, `event`, `handoff`, `close`) follows it:

1. While the run is active State holds one line `Run: orch run active; live record at <abs path
   of the ledger>` and no Task, Next or status copied from the ledger. Written by `start`,
   removed by `close` only; `handoff` keeps it.
2. Each merge adds one proof line to State: `Merged: <task> <short sha>; proof <command: result>`.
   `event` writes it in the merge turn.
3. After the last State edit of a step, run `.agents/skills/kis/scripts/state-stamp.sh <project
   root>` and write its output verbatim as the single `Stamp:` line near the top of State.
4. `close` flushes the ledger's Open decisions to Intent, removes the `Run:` line, restores Task
   and Next from the ledger, then stamps. `handoff` passes the decisions on in its packet.
5. Pointer off or no KIS: State is never touched by a run; the ledger is the whole record.
   Ledger and State never disagree about what is merged.

## Agents mode: the three rules

1. **Own nothing long-lived, and never block.** Agents run in Herdr panes. The watcher runs in
   its own visible pane via `herdr pane run`. The orchestrator starts no background jobs and does
   not wait: after each step it updates the ledger and ends its turn, so the user can always ask,
   start more agents or give feedback. When an agent finishes, needs the user, or closes, the
   watcher prompts the orchestrator with "orch event: ..." once it is idle with an empty input
   box (`commands/event.md`).
2. **The ledger is the memory.** `<repo>/.orch/ledger.md`, under 60 lines, shape in
   `ledger-template.md`. `scripts/orch-dir.sh` names the dir: it creates `.orch/` and keeps it out
   of git through `.git/info/exclude` (one entry serves every worktree; nothing is committed), and
   it keeps using an old `../<repo>.reports/orch/` while one exists, so a running run is never
   given a second ledger (`--migrate` moves it). Briefs, reports and handoffs live beside it in
   `.orch/<agent>/`. `Next action (<owner>):` has one line per orchestrator pane, never empty. Each
   orchestrator edits only its own rows and exact-matches its own Next action line; preserve
   other owners. Claim unowned legacy rows explicitly before acting. A fresh orchestrator orients
   from it alone. Agent-tool sub-agents die with the session, so long builds go in panes and
   sub-agents do one-message checks.
3. **Read verdicts, not output.** Pane reads `tail -10` at most. Reports and briefs by section
   (`sed -n '/## Result/,$p' | head -40`) or through a cheap sub-agent that returns one line.
   Artifact creation and status-space edits go to a sub-agent. Handoff replaces compact.

Integrations switch on when present and are skipped with one line when absent: KIS (`task` takes
items from `kis/intent/backlog.md`, agents run `/kis:plan` then `/kis:act`, `event` and `handoff`
follow the State contract); the user's status space over a notes MCP (one task per feature, a
plain thought per move, decisions starred; absent, the ledger's `Done this run` is the status).

## A run, end to end

`/orch:start`, pick Agents. `/orch:task <agent> <task>` per task, where the task is a KIS backlog
item, a status-space task, or the user's words: home (`references/placement.md`), brief file,
worktree, pane, pointer prompt, ledger row, watcher. The agent plans then acts in its worktree;
the orchestrator relays the plan's questions to the user one at a time and records the answers in
the ledger. End the turn after each step; on an "orch event" prompt, verify, merge, **close a
finished one-time agent; keep a multi-cycle stream such as design open** (`commands/event.md`
step 3), update the ledger, State per the contract, and the status space when it exists.
`/orch:status` whenever asked. `/orch:handoff` at about 150k. `orch:close` when the day's work ends.

Briefs are files under `.orch/<agent>/brief-<slug>.md`. The prompt is a pointer: "The user asked
for this: <one line>. Your brief is <path>. Read it in full and follow it. Write your report and
handoff to <path> and reply with a short summary, then continue straight into the plan."

## Commands

| Command | Does |
|---|---|
| `start` | Front door above. Agents mode: pick the run dir, orient from the ledger, reconcile with live state, print the board, re-prompt agents stopped by a limit, then do Next action. |
| `task` | One task to one named agent, which plans then acts in its worktree: brief, worktree and pane, pointer prompt, ledger row, watcher, plan questions relayed. |
| `status` | The board in under 20 lines: Next, Waiting on user, Parked, each agent's live state, last five events. |
| `handoff` | At about 150k context, or when asked: sync and check State (if KIS), ledger and handoff packet, start the successor, confirm it read the ledger, then say "close me". Read your own context by pane id: `herdr pane read <your pane id> --source recent-unwrapped --lines 8 \| grep -o 'ctx [^·]*'`. |
| `watch` | Start the watcher in its own pane, or add agents to the running one; record pane and pid. |
| `event` | Handle the watcher's "orch event" prompt: read each verdict, take the next ledger step, State per the contract, reply in five lines, end the turn. |
| `close` | The single close, built separately: agents, KIS sync and check, worktrees, commit and push. Follows the State contract. |

## Files

Agents mode loads these; none is read outside it.

- `ledger-template.md`: the run ledger's shape. `ledger-minimal-template.md`: the no-agent one.
- `references/tools.md`: every script and `orch-watch.py` subcommand, the sub-agents, `events.log`.
- `references/placement.md`: where work runs (sub-agent, new worktree pane, tab, helper pane).
- `references/runtimes.md`: per agent kind (claude, codex, cmd, agy): start, prompt, models.
- `references/brief-rules.md`: the standing rules every brief carries.
- `references/design.md`: the design stream. `references/visibility.md`: marks and check rules.
- Handoff packets: `<dir>/handoff-<date>-<n>.md`.

Proved 2026-10-07 with two Haiku test agents: a turn shorter than one poll is caught; a finish
while the orchestrator had typed text was held, then delivered within 30 s of the input
clearing. Not yet proved: a Codex orchestrator being woken, a watcher across a handoff, a long
run with several agents finishing together.
