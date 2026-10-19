# Current

Stamp: main bca1b05 f9aff0060c38

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
- Next: (1) owner live check of cycle 2: `orch adopt <agent> --role review` on the existing
  builder/reviewer, `orch list`, the board row, `orch close <name> --discard` leaves the pane;
  `prefix+b` (bound in `~/.config/herdr/config.toml` to `orch.board-full`, 2026-10-19; backup of
  the previous file in the session scratchpad) opens the board overlay, `q` closes it (not
  documented by Herdr for plugin overlays); one worktree spawn. (2) Phase 5 (skill). (3) Capture raw
  `HERDR_PLUGIN_EVENT_JSON` for one worker run to find the duplicate-notice root cause.
- Owner may delete the stale remote branch: `git push origin --delete orch-0.12.2`.
