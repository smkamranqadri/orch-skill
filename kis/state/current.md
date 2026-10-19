# Current

Stamp: main 378185f 5a26d70c0274

- Branch: `main` at `378185f`, pushed to `origin/main` 2026-10-19 (force-push of the rewritten
  history, 189 commits). No other branches or worktrees; all build and review agents are closed.
  `backup/pre-rewrite` is deleted. The remote branch `orch-0.12.2` still exists: the owner runs
  `git push origin --delete orch-0.12.2`. The old 0.12.2 build is gone from the tree (history
  `613aa67`); ideas worth keeping are in `kis/intent/ideas-from-0.12.2.md`.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-6 built, reviewed and
  merged, plus closed-row expiry (10 minutes), one board section per orch, ghost-orch reconcile,
  register with the live pane, and the pre-release review fixes (failed pane commands no longer
  mark orchs gone, re-adoption clears `closed_at`, queue totals of gone orchs stay visible, PTY
  board tests wait for output). The pre-release fixes were not re-reviewed.
- Blocker: none.
- Command: `./tests/run.sh` (180 tests, passing on `main`, 2026-10-19; about 300 s).
- Proof: suites re-run by the orchestrator after every merge. Live (2026-10-19): hook, worker
  spawn and notice delivery; `orch adopt`; `./bootstrap.sh update --repo <github url>` refreshed
  the skill copy and `check` passes. The plugin and the `orch` CLI link still point at this
  checkout: `update` refuses to replace a local plugin link with a GitHub install. Reviewers:
  Codex gpt-6.1-sol medium; builder GPT-6-Luna.
- Not verified live: `orch:*` commands in a fresh Claude Code and Codex session, the cap on a real
  clock (`orch resume`, `[cap] prompts_per_hour`), `prefix+b` overlay closing on `q`, a worktree
  spawn after the flag fix, a GitHub plugin install (needs `herdr plugin unlink orch` first),
  GitHub Actions, macOS and Bash 3.2. Duplicate notices are coalesced by a guard; the root cause
  is unknown (needs the raw event payloads of one worker run). The school-next failed start was
  traced only to the stale pane ID (fixed).
- Cosmetic: history shows two author identities (`T <t@example.invalid>` and the owner). The
  pre-rewrite commits were already public; GitHub Support can purge cached views.
- Next: (1) owner live checks above. (2) Owner tags a release and deletes `orch-0.12.2`. (3)
  Parked: the herdrctx-style board (its review found a missing title lookup timeout, a fixed
  8-column Project, titles ignoring the session prefix, flat agent rows), row select-and-enter,
  the idea list. Owner decision 2026-10-19: no more builder/reviewer loops for now.
