---
description: Handle the watcher's "orch event" prompt: read what changed, take the next ledger step for each agent, then end the turn so the user can type.
argument-hint: <the event text the watcher sent>
---

# Orch: event

Owner is your orchestrator pane id. One run and watcher serve all owners. Edit only rows
owned by you and exact-match `Next action (<owner>):` when updating it; preserve every other
owner's line. Legacy rows without an owner fall back to `<dir>/orchestrator`; claim them only
when that default is you: pin them with `move <dir> <agent>... --from <your pane id>
--orch <your pane id>` and record the owner in their ledger rows.

The watcher sends "orch event: <agent> finished (08:24); ..." when the orchestrator is idle with
an empty input box. It batches events that happened while the orchestrator was busy, so one
prompt can carry several agents.

1. If the prompt says "and N more", read events.log and filter agents by your current owner
   registrations. Read only your `orch=<owner>` entries in wake.md (legacy entries belong to
   the default owner). Preserve other owners' entries; process only your owned agents.
   Recheck ownership before acting: a handoff may have moved an agent since the prompt.
2. For each agent named, read its verdict, not its output (rule 3): `herdr agent read <agent>
   --source recent-unwrapped --lines 15 | tail -10`, or the handoff's `## Result` section.
   - finished with plan questions: `commands/task.md` step 9 (relay them to the user).
   - finished with a report: verify it (coordination rule 35) when the user has asked for a
     merge; otherwise record it and tell the user in one line.
   - needs you: it is waiting on a permission prompt or a question. Tell the user which agent
     and what it asks, in one line; never approve a permission prompt for them.
   - pane closed: mark the row gone; a resume brief means `commands/start.md` step 6.
3. **Close every finished one-time agent in the same turn (required, not optional).** Decide per
   agent: one-time (a docs pass, a check, a single fix) closes once its work is merged or its
   report recorded; a multi-cycle stream (design rounds, a build with review loops, an interview
   that will resume) stays open while more cycles are expected, because its context is useful,
   and its ledger row says "open: next cycle <what>". Close it too when the stream ends or its
   context passes about 200k (then a fresh agent starts from the handoff). Close it:
   - `python3 ~/.agents/skills/orch/scripts/orch-watch.py remove <dir> <agent>`
   - `herdr agent prompt <agent> "/exit"`, then `herdr worktree remove --workspace <ws>` (merged
     work only; with unmerged commits, keep the worktree and say so), and `git branch -d <branch>`
     (never `-D`).
   - Ledger: row status "closed", with the merge commit; events.log one line.
   Before ending any event turn, check your ledger rows: a row that is "done" or "merged" but neither
   "closed" nor "open: next cycle ..." is a missed step.
4. Update only your ledger rows and `Next action (<owner>):` line. When the repo has `kis/` and this event merged or
   closed work, rewrite `kis/state/current.md` in the same turn, inline (it is a few lines, not
   a sub-agent job): Task, Status, Proof as recorded in the ledger, and Next equal to the
   ledger's Next action for this owner. Preserve other owners' current State entries. The ledger and State must never disagree about what is merged; a
   handoff is too late to fix it. When the status space exists, give its task a one-line thought
   through a sub-agent (rule 49).
5. Reply in at most five lines: what changed, and what you need from the user, if anything.
   Then end the turn. Never wait in the foreground for the next event: the watcher will
   prompt again.
