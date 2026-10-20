# Current

Stamp: main cf805da deec612bbfaa

- Branch: `main` at `cf805da`. `origin/main` is at `8f7212b` (force-pushed 2026-10-19); the board
  merge `cf805da` and its State sync are NOT pushed (plain push, no force needed). No other branches or worktrees; all build and review agents are closed.
  `backup/pre-rewrite` is deleted. The remote branch `orch-0.12.2` still exists: the owner runs
  `git push origin --delete orch-0.12.2`. The old 0.12.2 build is gone from the tree (history
  `613aa67`); ideas worth keeping are in `kis/intent/ideas-from-0.12.2.md`.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-6 built, reviewed and
  merged, plus closed-row expiry (10 minutes), one board section per orch, ghost-orch reconcile,
  register with the live pane, and the pre-release review fixes (failed pane commands no longer
  mark orchs gone, re-adoption clears `closed_at`, queue totals of gone orchs stay visible, PTY
  board tests wait for output). The pre-release fixes were not re-reviewed.
  2026-10-20: herdrctx-style board (header, aligned Name/Status/Project/Title, a heading per
  project with its orchs below, `q quit` footer) and `orch board` (in place on a plain TTY, else
  the `board-full` overlay) built, reviewed once (1 round, 9 findings, fixed, fix commits not
  re-reviewed) and merged. Not seen live in Herdr: `orch board` from a plain shell and from an
  agent pane.
- Blocker: none.
- Command: `env -u HERDR_ENV -u XDG_STATE_HOME HOME=$(mktemp -d) ./tests/run.sh` (184 tests,
  passing on `main`, 2026-10-20; the PTY tests flake under heavy load, rerun one alone first).
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
- Open (owner 2026-10-20): false `idle`/`done` notices. Workers repeatedly report idle or done
  while still working (seen on every builder and reviewer run today), so the orch acts on a stale
  signal and shows `done` early. Check: capture the raw `pane.agent_status_changed` payloads for one
  run, compare with `herdr agent get`, then debounce in `plugin/hook.py` (confirm status is still
  idle after a short delay before notifying). Related to the duplicate-notice root cause above.
