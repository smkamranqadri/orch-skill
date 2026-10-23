# Current

Stamp: main 2d6e04a 1d2a941ffcd3

- Branch: `main`, pushed to `origin/main` 2026-10-23 (includes merge `2d6e04a` of `orch/notice-fix`).
  Version 1.0.0 (CHANGELOG, plugin manifest, board header); the owner tags `v1.0.0`. No other branches or worktrees; all build and review agents are closed.
  `backup/pre-rewrite` is deleted. The remote branch `orch-0.12.2` still exists: the owner runs
  `git push origin --delete orch-0.12.2`. The old 0.12.2 build is gone from the tree (history
  `613aa67`); ideas worth keeping are in `kis/intent/ideas-from-0.12.2.md`.
- Task: plan `kis/intent/plan-2026-10-23-notice-fixes.md`, Mode Standard: done and merged 2026-10-23
  (spawn pointer + start confirmation and `not-started`; reused-pane resolution; turn-based notices
  with `completion_seq`, a 15 s debounce and Herdr-restart reset; session-scoped close of reused
  resources). 2 review rounds (11 findings, all fixed); round 3 verified by the orch with the
  reviewer's 11 repros, no third review. Not released; CHANGELOG not updated.
  Earlier: plan `kis/intent/plan-2026-10-18-orch-v1.md` (v1, phases 1-6 and the 2026-10-20 board
  and close fixes) is done and merged. Caveats still open: the pre-release and board fix commits
  were not re-reviewed; `orch board` not seen live from a plain shell or an agent pane; `orch close`
  refuses a worktree holding only ignored `__pycache__` dirs unless `--discard` is passed.
- Blocker: none.
- Command: `env -u HERDR_ENV -u XDG_STATE_HOME HOME=$(mktemp -d) ./tests/run.sh` (233 tests,
  passing on `bdf96be` = `main` tree, 2026-10-23; the PTY tests flake under heavy load, rerun one alone first).
- Proof: suites re-run by the orchestrator after every merge. 2026-10-20: 1.0.0 installed with
  `./bootstrap.sh update --source .`, plugin reports 1.0.0, `check --source .` passes. Live (2026-10-19): hook, worker
  spawn and notice delivery; `orch adopt`; `./bootstrap.sh update --repo <github url>` refreshed
  the skill copy and `check` passes. The plugin and the `orch` CLI link still point at this
  checkout: `update` refuses to replace a local plugin link with a GitHub install. Reviewers:
  Codex gpt-6.1-sol medium; builder GPT-6-Luna.
- Live 2026-10-23 (Herdr 0.9.5, after the merge): a Claude (sonnet-5-5) and a Codex (gpt-6-luna)
  worktree worker each submitted the pointer by themselves, got exactly one `done` notice, no early
  `idle`; both closed cleanly. Not yet seen live: the debounce path (stop without `completion_seq`),
  `not-started`, Herdr-restart reset, the reused-pane close guard. Repros and restored briefs:
  `~/.local/state/orch-notice-fix/` (outside the repo, safe to delete after release).
- Live 2026-10-22 (fresh Claude Code session, unregistered): `orch:model` researched, asked,
  and wrote `~/.config/orch/matrix.md` after approval; `orch:close` reached `orch list`, which
  answers "caller is not a registered orch".
- Not verified live: the other `orch:*` commands in a fresh Claude Code session, all of them in
  Codex, the cap on a real
  clock (`orch resume`, `[cap] prompts_per_hour`), `prefix+b` overlay closing on `q`, a GitHub plugin install (needs `herdr plugin unlink orch` first),
  GitHub Actions, macOS and Bash 3.2. Duplicate notices are coalesced by a guard; the 2026-10-23
  probe found Herdr's false `done` blips and pane reuse (Knowledge), the likely causes. The school-next failed start was
  traced only to the stale pane ID (fixed).
- Cosmetic: history shows two author identities (`T <t@example.invalid>` and the owner). The
  pre-rewrite commits were already public; GitHub Support can purge cached views.
- Next: (0) owner decides the release for the notice fixes (CHANGELOG entry, version bump); next
  cycle is idea 16 (owner 2026-10-23). (1) owner live checks above. (2) Owner tags a release and deletes `orch-0.12.2`. (3)
  Parked: the herdrctx-style board (its review found a missing title lookup timeout, a fixed
  8-column Project, titles ignoring the session prefix, flat agent rows), row select-and-enter,
  the idea list. Owner decision 2026-10-19: no more builder/reviewer loops for now.
