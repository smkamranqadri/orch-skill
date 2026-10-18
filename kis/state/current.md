# Current

- Stamp: main 0cf718a be32462f93a8
- Branch: `main`. Source: orch 0.10.0, session-close 1.0.2, vendored KIS 0.11.0 (byte-identical
  to tag v0.11.0, vendored from GitHub 2026-10-18).
- Task: orch as the global front door, plan `kis/intent/plan-2026-10-17-orch-front-door.md`.
  Mode: Phase. Status: phases 0 and 1 done. KIS 0.11.0 released 2026-10-18: one squashed commit
  `f3b17bb` on KIS main, tag v0.11.0, pushed (verified from origin); all 9 KIS gates green on it.
  Six review rounds (last verdict ship); live anchor checks: Claude, Codex, agy turn 1, cmd turn 2.
- Blocker: none. This plan re-reviewed 2026-10-18 by Codex gpt-6.1-sol (high): pass 1 rework
  (1 blocker, 11 major, 2 minor), pass 2 after fixes 13 of 14 resolved, the last fixed; recorded in
  the plan's `## Review` (hash 2c86ee76814e), `plan-review.sh check` ok, mutant refused.
- Agents (owner, 2026-10-17): Herdr panes, reused across tasks, each replaced before 200k context.
  `kis-builder` Claude Sonnet 5.5 (effort per task: medium, high for task 4); `kis-reviewer`
  Claude Opus 5.5 (high, read and shell only). Reviewer rule: a different agent on a different
  model; the same host is fine. Picks come from `kis/knowledge/models.md`.
- Next: phase 2 (front door and close), starting with the interactive baseline. Propose
  builder and reviewer per kis/knowledge/models.md before launching.
  Follow-ups: lore's harvester records coordinator briefs sent to Herdr agents as owner
  corrections; KIS bootstrap warns "is not a commit" on an annotated tag; the KIS test fixture
  named `tartib` (a real product) predates 0.11 and should get a fictional name.
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
