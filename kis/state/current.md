# Current

Stamp: main 5bb839e 884f2ec0dc10

- Branch: `main` (phases 1, 2 and 4 merged, local only; old build in `archive/`). `main` is far
  ahead of `origin/main` (not pushed). `phase3-board-design` holds throwaway mockups, not merged.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-4 built and merged
  except the live steps of Phases 2 and 4. Board: owner chose direction B, project name dropped
  from rows (rows read `orch > agent`), "will improve after using it". Next phase: 5 (skill).
- Blocker: none.
- Command: `./tests/run.sh` (82 tests on `main`).
- Proof: phase 1 reviewed 4 rounds, phase 2 two, phase 4 two plus the orchestrator's own mutation
  check of the last change (Codex gpt-6.1-sol medium reviewer; builder GPT-6-Luna high); suite
  re-run by the orchestrator on `main`. The final project-free row change was not re-reviewed.
  Never run against live Herdr: dirty-worktree removal without `--force`, the `workspace not
  found` text, tab/pane parent-child removal, the plugin-pane open response and board
  detection, and the live Phase 2 and Phase 4 steps (checked on fakes, PTYs and fixtures only).
- Agents (Herdr, Codex, reused across tasks): `builder` GPT-6-Luna high in worktree
  `../orch-skill-wt/phase1` (pane w19:p1); `reviewer` GPT-6.1-Sol medium, workspace-write, cwd =
  session scratchpad so it can write its review file (pane w12:p16). Pipeline: builder starts the
  next task while the reviewer reviews the last; fixes are batched back to the builder; only P1
  findings block a merge.
- Next: (1) owner runs the live steps (`herdr plugin link "$PWD/plugin"`, one orch spawns one
  worker, check the notice and the board pane; commands in the worktree's untracked
  `HANDOFF.md`) and reports what differs. (2) Phase 5 (skill) via a builder brief; builder context
  is 16-54% and can be reused. (3) Fix what the live run shows.
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
