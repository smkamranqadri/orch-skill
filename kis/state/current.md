# Current

Stamp: main cc08e86 076d7043b71e

- Branch: `main` (phase 1 merged, fast-forward, local only; old build in `archive/`). `main` is far
  ahead of `origin/main` (not pushed). Phase 2 is on `phase2-push` (commit `f8a8005`, on top of
  phase 1), not merged.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phase 1 (core CLI) done and merged.
  Phase 2 (push) built, under review.
- Blocker: none.
- Command: `./tests/run.sh` (phase 1: 42 tests; `phase2-push`: 57).
- Proof: phase 1 reviewed in 4 rounds (Codex gpt-6.1-sol medium; findings 9, 6, 1, then ship),
  guards mutation-checked by builder and reviewer, suite re-run by the orchestrator. Never run
  against live Herdr: dirty-worktree removal without `--force`, the `workspace not found` error
  text, and tab/pane parent-child removal were checked on fakes only.
- Agents (Herdr, Codex, reused across tasks): `builder` GPT-6-Luna high in worktree
  `../orch-skill-wt/phase1` (pane w19:p1); `reviewer` GPT-6.1-Sol medium, workspace-write, cwd =
  session scratchpad so it can write its review file (pane w12:p16). Pipeline: builder starts the
  next task while the reviewer reviews the last; fixes are batched back to the builder; only P1
  findings block a merge.
- Next: (1) read `review-phase2.md` from the reviewer and send fixes to the builder if "fix first";
  merge `phase2-push` to `main` on "ship". (2) Owner runs the Phase 2 live step (commands in the
  worktree's untracked `HANDOFF.md`). (3) Phase 3 board design: render directions as real text in
  a Herdr terminal pane (no Pencil, owner's call 2026-10-19), screenshot, owner picks one.
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
