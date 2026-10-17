# Current

- Branch: `main`, in step with `origin/main` (public). Source: orch 0.10.0, session-close 1.0.2,
  vendored KIS 0.10.1. No code change since 43eed48.
- Task: orch as the global front door, plan `kis/intent/plan-2026-10-17-orch-front-door.md`.
  Mode: Phase. Status: phase 1 in progress (KIS 0.11.0, worktree
  `../kis-loop-skill.wt/kis-0.11`, branch `kis-0.11`). Done on the branch: task 1 State stamp
  (`5a3aa78`, `7ea6ebe`), task 2 plan review (`bda1469`, `0c29a80`, `bd81360`), task 3 Run pointer
  (`16e08d3`); each re-verified by the coordinator (gates and probes). Task 4 (anchors on four
  hosts) is with the builder; tasks 1-3 await the Opus review.
- Blocker: none.
- Agents (owner, 2026-10-17): Herdr panes, reused across tasks, each replaced before 200k context.
  `kis-builder` Claude Sonnet 5.5 (effort per task: medium, high for task 4); `kis-reviewer`
  Claude Opus 5.5 (high, read and shell only). Reviewer rule: a different agent on a different
  model; the same host is fine. Picks come from `kis/knowledge/models.md`.
- Next: Opus review of tasks 1-2, then 3 and 4; live anchor checks on each host in the test home;
  task 5 release 0.11.0 and vendor here. When vendored, this plan needs a `## Review` record in
  the new format or `kis:act` refuses it.
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
