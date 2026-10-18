# Current

- Stamp: main c63c4cd fd2131ae3782
- Branch: `main` (local, NOT pushed): c63c4cd merges phases 2-3. orch 0.12.0 installed in the real
  home 2026-10-18 (`bootstrap.sh update --source .`, check rc 0; Codex prompts, cmd commands, agy skill
  link wired). Vendored KIS 0.11.0. Board plugin linked in the real Herdr from the p3 worktree path
  (`herdr plugin unlink orch` to remove; relink from skills/orch/plugin before deleting worktrees).
- Task: plan `kis/intent/plan-2026-10-17-orch-front-door.md`, Mode Phase. Phases 0-3 done (2-3 merged;
  the last fix commits 33012a5..4187677, 0d86a47, 6c750c3, dbc6518 passed tests and coordinator reruns
  but had no separate review, stopped to save quota). Phase 2 live: Claude, Codex, cmd pass start, fix,
  close and recovery headless; agy (gpt-oss) treats "orch" as a shell binary (open). Phase 3 live run in
  Herdr not done (event hook verified firing on a real Herdr event).
- Blocker: none.
- Next: phase 4, owner decision 2026-10-18 "move all, delete nothing": per repo (example-app, tartib,
  anjuman-sadat-una-junagadh) move `<repo>.reports/orch/` to `<repo>/.orch/run-legacy/` and every other
  folder in `<repo>.reports/` to `<repo>/.orch/legacy/` (same disk, rename); the stale wakes (example-app
  4, tartib 2, from 2026-10-09) are archived, not replayed; no legacy watcher is running; repair KIS files
  citing the old path (example-app: kis/intent/roadmap.md, kis/intent/feedback-r1.md,
  kis/state/current.md, kis/knowledge/technical.md; tartib: kis/state/current.md,
  kis/intent/space-descriptions.md); check each repaired target resolves; remove only the then-empty
  `.reports` dir; verify `orch:start` recovers each. Then remove the legacy path from orch-dir.sh,
  start.md, SKILL.md and the watcher (one small builder), tests green. Then phase 5 (probes updated per
  [3.11], rerun; ask the owner about quota first: cmd and agy live runs cost 1-3.5M tokens each).
  Owner's quota is low: prefer the cheapest path and say the cost before any agent or live run.
- Agents (owner, 2026-10-17): Herdr panes, reused across tasks, each replaced before 200k context.
  `kis-builder` Claude Sonnet 5.5 (effort per task: medium, high for task 4); `kis-reviewer`
  Claude Opus 5.5 (high, read and shell only). Reviewer rule: a different agent on a different
  model; the same host is fine. Picks come from `kis/knowledge/models.md`.
- Test home: `~/.cache/orch-skill-test-home/home` (orch 0.10.0, session-close 1.0.2, lore 1.0.0,
  memory files copied without the hub config, Herdr skill), with the owner's Claude, Codex and
  cmd credential files linked (agy uses the keyring). Live runs: `scripts/measure-live.py run
  --home <test home> --out <dir>`.
- Proof on record: plan reviewed twice 2026-10-17 by Codex gpt-6.1-sol (high, read-only). Pass 1:
  rework (1 blocker, 11 major, 1 minor); pass 2: ready after fixes (10 major, 1 minor); all
  folded in. Re-checked by hand: the PreCompact blocker (Claude hooks docs), the watcher finding
  (`orch-watch.py:454`) and per-repo KIS delivery (`install-skill.sh:110`, KIS README).
- Machine: fresh Linux laptop (2026-10). orch and session-close are **not installed** here. In
  `~/.agents/skills`, linked for Claude and agy: lore 1.0.0, herdr (upstream 143bf5f; CLI 0.9.5)
  and humanizer 3.1.0. The earlier setup and its `.orch/` proof logs stay on the owner's Mac.
- Research: doc "Agent Stack Landscape Report"
  (https://claude.ai/code/artifact/461cac36-c255-4f21-b056-fe80a896c54f); raw files in
  `.orch/research-2026-10-16/` (untracked, not git-ignored: never stage it).
- Command: `tests/run.sh` (green 2026-10-17 on Linux with `ORCH_TEST_NO_LIVE=1`, after two
  `stat` order fixes in tests); `ORCH_TEST_NO_LIVE=1` skips live Codex probes;
  `./bootstrap.sh check --source .`.
- Older open items: `kis/intent/backlog.md` (re-triage in the plan's phase 5).
