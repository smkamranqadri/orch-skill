# Current

Stamp: main 8baf38c f9aff0060c38

- Branch: `main` (phases 1, 2, 4, the live fixes and cycle 2 merged, local only; old build in
  `archive/`). `main` is far ahead of `origin/main` (not pushed). `phase3-board-design` holds
  throwaway mockups, not merged.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-4 built and merged.
  Cycle 2 (owner's board polish, `orch adopt`, `board-full` overlay action) merged. Next: owner's
  live check of cycle 2, then Phase 5 (skill).
- Blocker: none.
- Command: `./tests/run.sh` (109 tests on `main`).
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
- Next: (1) Phase 5 (skill) now, with a cap on automatic orch work (owner, 2026-10-19: pushed
  notices make the orch run on its own, so an away owner could burn the whole quota): plugin
  circuit breaker on delivered prompts per hour plus skill rules (work only inside an approved
  plan, a per-approval prompt budget, at most 2 review rounds per task, then stop and report).
  (2) `board-v2` (herdrctx-style tree, `7dcbfee`) is NOT merged: reviewer found 1 P1 (title lookup
  `herdr pane list` has no timeout; freezes board and `q`) and 3 P2 (Project fixed at 8 columns,
  titles ignore the session prefix, agents not indented under their orch); the builder was closed
  by the owner before its fixes landed. Owner decided to stop that loop for now; `main` keeps the
  old table board. (3) Owner live checks (see earlier list; `prefix+b` overlay and `q`, worktree
  spawn). (4) Capture raw `HERDR_PLUGIN_EVENT_JSON` for one worker run (duplicate-notice cause).
  Live 2026-10-19: `orch adopt` works; a worker finishing wakes the orch with a notice, adopted or
  spawned.
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
