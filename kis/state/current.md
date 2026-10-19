# Current

Stamp: main c6c4ac9 884f2ec0dc10

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
- Next: (1) finish the live fixes on branch `live-fixes` (builder): board pane dies with
  `--cwd`, every notice queued twice (done and closed), `orch spawn --where worktree` passes
  `--workspace` and `--cwd` together (invalid in Herdr 0.9.5); then re-verify live. Delivery to a
  live idle orch already works (2026-10-19). (2) Next cycle, owner's board list: add a `closed`
  state and glyph and do not count closed agents/gone orchs in the header; drop the legend; add
  blank lines between orch groups; drop the registry path from the footer (keep refresh time);
  show the HOST / MODEL column also in narrow panes if it fits. (3) Next cycle, new command:
  `orch adopt <agent|pane>` registers an agent not started by orch (builder, reviewer) from
  `herdr agent get`, owned by the caller, `created` empty so close never removes its pane. (4)
  Phase 5 (skill).
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
