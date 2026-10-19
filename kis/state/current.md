# Current

Stamp: main 94a12f4 6aa01e7e085a

- Branch: `main` (phases 1 and 2 merged, local only; old build in `archive/`). `main` is far
  ahead of `origin/main` (not pushed). Phase 3 mockups are on `phase3-board-design`, not merged.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1 and 2 done and merged
  except Phase 2's live step. Phase 3 (board design): three directions A grouped tree, B flat
  table, C project cards rendered by `design/board/render.py` on `phase3-board-design`; owner is
  choosing.
- Blocker: none.
- Command: `./tests/run.sh` (61 tests on `main`).
- Proof: phase 1 reviewed in 4 rounds, phase 2 in 2 (Codex gpt-6.1-sol medium; findings 3 then
  ship), guards mutation-checked by builder and reviewer, suite re-run by the orchestrator. Never
  run against live Herdr: dirty-worktree removal without `--force`, the `workspace not found`
  error text, tab/pane parent-child removal, and the Phase 2 live step (plugin link, real orch
  and worker) were checked on fakes and recorded fixtures only.
- Agents (Herdr, Codex, reused across tasks): `builder` GPT-6-Luna high in worktree
  `../orch-skill-wt/phase1` (pane w19:p1); `reviewer` GPT-6.1-Sol medium, workspace-write, cwd =
  session scratchpad so it can write its review file (pane w12:p16). Pipeline: builder starts the
  next task while the reviewer reviews the last; fixes are batched back to the builder; only P1
  findings block a merge.
- Next: (1) owner picks a board direction (A, B or C; builder recommends A); then Phase 4 build.
  (2) Owner runs the Phase 2 live step (commands in the worktree's untracked `HANDOFF.md`).
  (3) Replace the `builder` agent with a fresh one before its next task (context 70%).
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
