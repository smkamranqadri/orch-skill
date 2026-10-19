# Current

Stamp: main 9c7d833 3b13b9288f59

- Branch: `main` (phases 1, 2, 4, the live fixes and cycle 2 merged, local only; old build in
  `archive/`). `main` is far ahead of `origin/main` (not pushed). `phase3-board-design` holds
  throwaway mockups, not merged.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-5 built and merged (phase 5: skill plus the notice cap, not reviewed by the reviewer,
  orchestrator read the skill and the cap code).
  Cycle 2 (owner's board polish, `orch adopt`, `board-full` overlay action) merged. Next: owner's
  live check of cycle 2, then Phase 5 (skill).
- Blocker: none.
- Command: `./tests/run.sh` (113 tests on `main`).
- Proof: phases 1, 2, 4 and cycle 2 reviewed in rounds (Codex gpt-6.1-sol medium reviewer; builder
  GPT-6-Luna high); suite re-run by the orchestrator on `main`. The `board-full` overlay change
  was not reviewed separately. Live (2026-10-19): hook runs, worker spawn and delivery to an idle
  orch work; `--cwd` board open, duplicate notices and worktree-create flags were found live and
  fixed. Still unverified live: `orch adopt`, `board-full` closing on `q`, worktree spawn after the
  fix, narrow-pane captures in the real pane, the fix for duplicate notices (a coalescing guard,
  root cause not found; needs the six raw event payloads of one worker run).
- Agents (Herdr, Codex, reused across tasks): `builder` GPT-6-Luna high in worktree
  `../orch-skill-wt/phase1` (pane w19:p1); `reviewer` GPT-6.1-Sol medium, workspace-write, cwd =
  session scratchpad so it can write its review file (pane w12:p16). Pipeline: builder starts the
  next task while the reviewer reviews the last; fixes are batched back to the builder; only P1
  findings block a merge.
- Next: (1) owner live checks, now including the skill (Phase 5 live: `orch:start` in a repo with
  KIS and in a scratch repo without, `orch:plan` spawns a planner, `orch:close` asks before
  removing a merged worktree, on Claude Code and Codex; the skill is at `skills/orch/` and must be
  made visible to each CLI) and the cap (`orch resume`, `[cap] prompts_per_hour`), `prefix+b`
  overlay and `q`, one worktree spawn. (2) Phase 6 (release: packaging, README, install, public
  repo review before any push). (3) Parked: `board-v2` (see below), raw event capture for the
  duplicate-notice cause. Owner decision 2026-10-19: no more builder/reviewer loops for now.
- `board-v2` (herdrctx-style tree, `7dcbfee`, not merged): reviewer found 1 P1 (title lookup has
  no timeout), 3 P2 (Project fixed at 8 columns, titles ignore the session prefix, agents not
  indented); fixes never landed (builder closed by the owner).
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
