---
description: Close the session in one pass: close agents when a run is active, sync and check project memory, clean merged worktrees and branches, then commit and push only as the rules allow.
argument-hint: [apply]
---

# Orch: close

The single end-of-session routine, in any repo, with or without `kis/` or a run. Run the steps in
order without asking between them. Skip a step whose tool or folder is absent, say so in one
line, and never fail the whole close on one missing piece. `apply` as the argument applies the
KIS check's cleanup without a second yes; otherwise showing that proposal is the only question
the close asks.

Full method: `~/.agents/skills/orch/SKILL.md`. The handoff command reuses steps 3, 4, 5 and 7 below.

1. **Close agents** (only when a run is active). A run is active when the run dir
   (`D=$(~/.agents/skills/orch/scripts/orch-dir.sh --check)`) holds a `ledger.md` with a row
   whose status is not `closed`, `merged` or `gone`. None: skip to step 3. For each agent that is
   still alive, ask for its handoff note, copy its worktree's gitignored reports somewhere
   durable, then close the pane and the workspace. Agents owned by another orchestrator are
   left alone and named. Then stop the watcher
   (`kill $(cat <D>/watcher.pid)`, confirm with `kill -0`) and mark the ledger `Run closed
   <date>`.
2. **End the run's records** (only when step 1 ran). With `kis/`: delete the `Run:` line from
   `kis/state/current.md`, and move the ledger's Open decisions into the plan in `kis/intent/`
   (or `kis/intent/backlog.md` when no plan fits), each as the user's words with its date. Done
   items already hold a proof line in State; leave them. Without `kis/`: the ledger stays as the
   record and keeps its Open decisions and Done lines for the next session.
3. **Sync project memory.** With a `kis/` folder, run the KIS sync step (`/kis:sync`, or
   `.agents/skills/kis/commands/sync.md`), working from `git status` and `git diff`, not
   memory. No `kis/`: skip steps 3 to 5 and say so. A `Run:` line still in State (another
   session's run) is kept, never rewritten.
4. **Check project memory.** Run the KIS check step (`/kis:check`, or `commands/check.md`).
5. **Apply the check.** With `apply`, apply the proposed cleanup at once; otherwise show the
   proposal and wait for a yes. Then write the State stamp as the last State write:
   `.agents/skills/kis/scripts/state-stamp.sh <project root>` (the directory that holds `kis/`),
   its output verbatim as the single `Stamp:` line near the top of State. Stamp again after any
   later State edit.
6. **Remove merged worktrees and branches.** List `git worktree list` and `git branch`. For each
   one other than the current, run `git log <main>..<branch>` and `git status --short` inside it
   first. Remove only a branch with zero unmerged commits and a worktree with no uncommitted or
   untracked files. Keep the rest, and any folder an app holds open with unsaved edits, naming
   each one kept and why. Never `git worktree remove --force` and never `git branch -D`.
7. **Update the project's status space** when the project has one in the notes backend: one task
   per feature, open or done, with a one-line plain-language thought for each feature that moved
   this session, and decisions waiting on the user starred. No status space or backend: skip.
8. **Leave no work orphaned.** If work is unfinished and a fresh session must pick it up, State's
   Task and Next already say so after the sync; with no `kis/`, write the next action into the
   ledger now.
9. **Commit and push** only when the user asked for it in this session or the repo's own rules
   direct it; a rule against committing wins. Read `git status`, stage explicit paths, read the
   commit message back before committing, push, and confirm the tree is clean and level with the
   remote. Otherwise commit nothing and list what is uncommitted.
10. **Say plainly what is left**: anything uncommitted, any branch or folder kept, any step
    skipped.

## Report

One line per step: done, skipped and why, or kept and why. Then what is uncommitted, in full.
Nothing else; the user is about to close the window.
