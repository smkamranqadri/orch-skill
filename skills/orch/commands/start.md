---
description: Front door for any repo. With kis/, run KIS's start step and add one mode, Agents. Without kis/, install KIS or use the minimal ledger. In Agents mode, orient from the run ledger and do the Next action.
argument-hint: [optional task or focus, or a ledger dir for Agents mode]
---

# Orch: start (also resume)

Full method: `~/.agents/skills/orch/SKILL.md`. Act without asking beyond the one confirmation
below. Herdr is needed only in Agents mode; the other modes never touch it.

## 1. Which memory

- **Repo has `kis/`**: version check, then KIS's start.
  1. `~/.agents/skills/orch/scripts/orch-kis-version.sh`. Exit 0: go on. Exit 3 (below 0.11.0, or
     unreadable) or exit 2 with `kis/` present (no `.agents/skills/kis`): before offering, read
     `$(~/.agents/skills/orch/scripts/orch-dir.sh --check)/ledger.md` if it exists and is not
     marked `Run closed`; a `State pointer: off (KIS <v>)` line whose `<v>` is the version the
     script printed (`none` for exit 2) means the user already declined this: skip the offer and
     treat it as declined. Otherwise offer that repo's one-line update or install
     (`bootstrap.sh update` from KIS's README, run from the repo) and continue without it if the
     user declines. Declined: "pointer off" for this run (SKILL.md, State contract); an Agents
     run records it in the ledger (step 3.1). Declined at exit 2 there is no KIS start step to
     run: say so in one line, read `kis/state/current.md` directly (if it exists) for Task and
     Next, report them, propose the mode as step 3 does, and skip step 2.
  2. Run the repo's KIS start step, `.agents/skills/kis/commands/start.md`, unchanged (not after a
     declined exit 2): it reads State (and follows a `Run:` pointer), prints its report and
     proposes a mode.
  3. Reuse that report's one mode proposal and its single confirmation. Add one mode to the
     list: **Agents** (several agents in Herdr panes with a watcher). Never ask a second mode
     question. Fast, Standard and Phase continue as KIS says; nothing below runs.
- **No `kis/`**: say so in one line and offer once: install KIS (the repo's one-line bootstrap
  from KIS's README), or run on the minimal ledger. Install: do it, then take the branch above.
  Minimal ledger: step 2.

## 2. Minimal ledger (no KIS, not Agents mode)

`D=$(~/.agents/skills/orch/scripts/orch-dir.sh)`. No `$D/ledger.md`: copy
`~/.agents/skills/orch/ledger-minimal-template.md` there and fill Task and Next action from the
user's words. Otherwise read it and report Task, Next action, Plan review, Decisions, Done in
five lines. Run `python3 ~/.agents/skills/orch/scripts/orch-watch.py check $D`.

Plan review (no KIS). Fast-mode work (a small, obvious fix) needs no written plan: leave
`Plan: none` and `Plan review: none`, and never write a plan file just to satisfy `check`. When
the session wrote a plan for Standard or Phase work (a file, not a chat sketch), it is reviewed
before any implementation. Propose the reviewer to the user (a different CLI than the plan's
author; harness, model and effort, with a reason) and launch it only after they approve; never
start another CLI on your own. Run the review read-only, relay the findings, and record `Plan:`
and `Plan review: <reviewer>; outcome: ready|rework; <date>` in the ledger (pick one outcome).
Do not implement while `check` reports `[plan-review]`; `outcome: rework` goes back to the
author, then a new review. If the review cannot run (the reviewer stalls, times out or is
missing), do not wait on it: write `Plan review: blocked; <reason>; <date>` in the ledger and ask
the user once: review later, waive (record `outcome: waived` with their words under Decisions),
or stop.

## 3. Agents mode (Herdr required)

Herdr missing (`herdr` not on PATH or `HERDR_ENV` unset): say so in one line and stop this mode;
the user installs it or picks another mode. Otherwise read `SKILL.md` "Agents mode" and load
`ledger-template.md`, `references/` and `commands/watch.md` only now.

Owner is your orchestrator pane id. One run and watcher serve all owners. Edit only rows
owned by you and exact-match `Next action (<owner>):` when updating it; preserve every other
owner's line. Legacy rows without an owner fall back to `<dir>/orchestrator`; claim them only
when that default is you: pin them with `move <dir> <agent>... --from <your pane id>
--orch <your pane id>` and record the owner in their ledger rows.

1. Run dir: `$ARGUMENTS`, or `D=$(~/.agents/skills/orch/scripts/orch-dir.sh)` from the repo
   root. It creates `.orch/` (excluded from git) or, while an old `../<repo>.reports/orch/`
   run exists, names that one and creates nothing; migrate only when the user asks
   (`orch-dir.sh --migrate`). Read the ledger `$D/ledger.md`. A `Ledger: minimal` ledger is
   upgraded: copy `ledger-template.md` over it, keeping Task as the first Next action and
   moving its Decisions and Done into the matching sections.
   A ledger marked `Run closed <date>` belongs to a finished run: rename it `ledger-<date>.md`
   (add `-2`, `-3` if that name exists), then treat it as no ledger, so the new run starts from
   the template without the old `Run closed` or `State pointer:` lines.
   Pointer off: put `State pointer: off (KIS <version>)` on the line under `Updated:`; step 1.1
   reads that line, so a successor in the same run is not offered the update again.
   No ledger: copy `ledger-template.md` there, fill it from State (if any) and
   `scripts/orch-agents.sh`, and set your Next action from State's Next. No State or no Next:
   set Next action to "ask the user for the first assignment", print the board, and ask in one
   line; then `/orch:task` does the rest.
2. State pointer (KIS >= 0.11 only, and not "pointer off"): set State's `Run:` line to
   `Run: orch run active; live record at <abs path of $D/ledger.md>` (absolute on purpose: a
   linked worktree shares the main checkout's `.orch/`). First move State's Task and Next into
   the ledger's Next action, so State holds neither during the run; then write the stamp
   (SKILL.md, State contract). Pointer off or no KIS: write nothing into State.
3. Reconcile your owned rows with `scripts/orch-agents.sh` and `git worktree list`. Fix only
   yours. Do not claim live agents owned elsewhere or adopt every agent with no row. Joining an
   existing run adds your Next action line; it never resets the ledger or wake default.
4. Check the watcher: `kill -0 $(cat <dir>/watcher.pid)`. Dead or missing: run `commands/watch.md`.
   Alive: leave its default unchanged. Register only your agents with
   `python3 ~/.agents/skills/orch/scripts/orch-watch.py add <dir> <agent>... --orch <your pane id>`.
   Already registered agents retain their owner; use guarded `move` to transfer them.
5. Print the board (`commands/status.md`), then run
   `python3 ~/.agents/skills/orch/scripts/orch-watch.py check <dir> --owner <your pane id>` and
   fix the findings for your own rows and your Next action first (the ledger over 60 lines, a
   done agent never closed, a missing row); report run-wide findings you do not own in one line.
6. For each of your agents whose status is stopped by a limit or gone with a resume brief,
   re-prompt it from that brief: "The user asked for this: resume. Your brief is <handoff or
   resume brief>. Read it in full and continue." Record the prompt as its last event.
7. Do the Next action. Then update the ledger, including the new Next action, and end the turn;
   the watcher prompts you on the next event.

Started by a handoff: use the packet's source-owner Next action until transfer; do not claim
its agents or add a competing Next action. Stop after step 5, reply with the board and the Next
action, and act only on "go". Until then only the old owner may act on the transferred stream;
other owners continue.
