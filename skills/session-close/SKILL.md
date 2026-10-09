---
name: session-close
description: "Close a working session in the user's fixed order: sync and check project memory (KIS), apply the check, close agent workspaces and remove merged worktrees and branches, update the project's Tartib space, run the lore retrospective, confirm no handoffs are left, then commit and push. Use when the user says close the session, wrap up, end of session, or asks for the closing routine. Each step runs without asking; only the KIS cleanup waits for a yes unless the user said apply."
metadata:
  version: "1.0.1"
---

# Session close

The user's end-of-session routine, from preferences 30 and 32 in the Tartib space `ai-agents`.
Run every step in this order without asking between them. Skip a step only when its tool or
folder is absent, and say so in one line. Never fail the whole close on one missing piece.

Argument: `apply` means the KIS check's cleanup is applied without a second yes.

Claude Code: `/session-close [apply]`. Codex and other agents: "run the session close" and
follow this file.

## Steps

1. **Sync project memory.** If the repository has a `kis/` folder, run the KIS sync step
   (Claude `/kis:sync`; otherwise follow `.agents/skills/kis/commands/sync.md`). Establish what
   changed from `git status` and `git diff`, not memory. No `kis/`: skip 1 to 3 and say so.
2. **Check project memory.** Run the KIS check step (`/kis:check`, or `commands/check.md`).
3. **Apply the check.** With the `apply` argument, apply the proposed cleanup at once. Without
   it, show the proposal and wait for a yes; this is the only question the close asks.
4. **Close agents** (only when this session ran other agents). Ask each for a handoff note,
   run its retro, copy every worktree's gitignored reports somewhere durable, then close the
   workspaces.
5. **Remove merged worktrees and branches.** For each worktree and branch, check
   `git log main..<branch>` first. Remove only those with zero unmerged commits and a clean
   tree. Keep any branch with unmerged work, and any folder an app holds open with unsaved
   edits (for example Pen); name each one kept and why. Never `git worktree remove --force`.
6. **Update the project's Tartib space.** One task per feature, open or done, with a one-line
   plain-language thought for each feature that moved this session (merged, released, paused),
   and decisions waiting on the user starred (preference 33). Tartib tools absent: skip and
   say so.
7. **Retrospective.** Run the lore retro (`/lore:retro`, or the Retrospective step of
   `~/.agents/skills/lore/SKILL.md`). Do this before any compact (core rule 66).
8. **Confirm no handoffs are left.** If work is unfinished and a fresh session must pick it up,
   write a handoff note in the project's memory now.
9. **Commit and push.** Read `git status`, stage explicit paths, read the commit message back
   before committing, push, and confirm the tree is clean and in step with the remote
   (core rule 38). A pre-existing rule in the project against committing wins over this step.
10. **Say plainly what is left.** Anything uncommitted, any branch or folder kept, any step
    skipped.

## Report

One line per step: done, skipped and why, or kept and why. Then what is uncommitted, in full.
Nothing else; the user is about to close the window.
