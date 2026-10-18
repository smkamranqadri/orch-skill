# Current

- Stamp: main 693da06 1cca1e56b45f
- Branch: `main` (local, NOT pushed; code tip 5dfac31). orch 0.12.2 installed in the real home
  2026-10-18 (`bootstrap.sh update --source .`, check rc 0; Codex prompts, cmd commands, agy skill
  link wired). Vendored KIS 0.11.0. Board plugin linked in the real Herdr from the p3 worktree path
  (`herdr plugin unlink orch` to remove; relink from skills/orch/plugin before deleting worktrees).
- Task: plan `kis/intent/plan-2026-10-17-orch-front-door.md`, Mode Phase. Phases 0-4 done. Open
  from phase 2: agy (gpt-oss) treats "orch" as a shell binary. Open from phase 3: live run in
  Herdr not done (event hook verified firing on a real Herdr event). Open review minor:
  `orch-gate.py archive` tracebacks on a `/` in the `Run closed` date.
- Blocker: none.
- Next: phase 5 (probes updated per [3.11], rerun; ask the owner about quota first: cmd and agy
  live runs cost 1-3.5M tokens each). Owner's quota is low: prefer the cheapest path and say the
  cost before any agent or live run.
- Phase 4 proof (2026-10-18): example-app, tartib and anjuman-sadat-una-junagadh moved by hand,
  delete nothing: `<repo>.reports/orch/` is `<repo>/.orch/run-legacy/`, other folders in
  `<repo>/.orch/legacy/` (bytes identical per repo); no legacy watcher was alive; `.reports` dirs
  removed; every citing file repaired and each target resolves; `orch-dir.sh --check` resolves
  `<repo>/.orch` in all three. The repairs are uncommitted in those repos (owner commits; tartib
  also has unrelated uncommitted work). All three run KIS 0.10.1 (orch:start offers the update).
  Not done: a live `orch:start` in each. Code: legacy path removed `dcf9996` (merge 091c41d);
  kis-reviewer (Opus 5.5 high) review: ready, plus a major in the phase 3 fixes (`merged()` took
  "closed: not merged" as landed), fixed with three minors in `842683f` (merge 5dfac31), re-review
  ready; tests rc 0 rerun by the coordinator after each merge.
- Proof on record: plan reviewed twice 2026-10-17 by Codex gpt-6.1-sol (high, read-only). Pass 1:
  rework (1 blocker, 11 major, 1 minor); pass 2: ready after fixes (10 major, 1 minor); all
  folded in. Re-checked by hand: the PreCompact blocker (Claude hooks docs), the watcher finding
  (`orch-watch.py:454`) and per-repo KIS delivery (`install-skill.sh:110`, KIS README).
- Research: doc "Agent Stack Landscape Report"
  (https://claude.ai/code/artifact/461cac36-c255-4f21-b056-fe80a896c54f); raw files in
  `.orch/research-2026-10-16/` (untracked, not git-ignored: never stage it).
- Command: `tests/run.sh` (green 2026-10-18 on Linux with `ORCH_TEST_NO_LIVE=1`);
  `ORCH_TEST_NO_LIVE=1` skips live Codex probes; `./bootstrap.sh check --source .`.
- Older open items: `kis/intent/backlog.md` (re-triage in the plan's phase 5).
