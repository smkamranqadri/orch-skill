# Current

- Branch: `main`, in step with `origin/main` (public). Source: orch 0.10.0, session-close 1.0.2,
  vendored KIS 0.10.1. No code change since 43eed48.
- Task: orch as the global front door, plan `kis/intent/plan-2026-10-17-orch-front-door.md`.
  Mode: Phase. Status: plan approved 2026-10-17, **not started** (owner: write, do not start).
- Blocker: none.
- Next: on the owner's go, Phase 0 (baseline probe and live cases in an isolated test home).
  Before each implementer or reviewer call, propose harness, model and effort for approval.
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
- Command: `tests/run.sh`; `ORCH_TEST_NO_LIVE=1` skips live Codex probes;
  `./bootstrap.sh check --source .`.
- Older open items: `kis/intent/backlog.md` (re-triage in the plan's phase 5).
