# Current

- Branch: `main`, in step with `origin/main` (public). Source: orch 0.10.0, session-close 1.0.2,
  vendored KIS 0.10.1. No code change since 43eed48.
- Task: orch as the global front door, plan `kis/intent/plan-2026-10-17-orch-front-door.md`.
  Mode: Phase. Status: phase 0 nearly done (owner's go 2026-10-17). Static and live baselines in
  `kis/knowledge/start-cost.md`; agy's `resume-reopen` and `no-kis` wait on its quota.
- Blocker: agy plan quota (429) until about 2026-10-24; only those two agy cases.
- Next: owner reviews the phase 0 commit; then phase 1 (KIS 0.11.0 in ../kis-loop-skill).
  Before each implementer or reviewer call, propose harness, model and effort for approval.
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
