# Current

Stamp: main 4566cd9 2b5f87a2653f

- Branch: `main`, pushed to `origin/main` 2026-10-24 (includes merge `7d4508b` of `orch/proof-build`).
  Version 1.1.0 (CHANGELOG, plugin manifest, board header), released 2026-10-24 as tag `v1.1.0`
  and a GitHub release (1.0.1 likewise 2026-10-23); `v1.0.0` is a tag only. No other branches or worktrees, local or remote
  (`orch-0.12.2` is gone); all build and review agents are closed. The old 0.12.2 build is gone from the tree (history
  `613aa67`); ideas worth keeping are in `kis/intent/ideas-from-0.12.2.md`.
- Task: plan `kis/intent/plan-2026-10-23-proof-handoffs.md` (idea 16), Mode Standard: done, merged and
  released in 1.1.0 2026-10-24. Proof rules appended by spawn,
  `--test-cmd`, `orch verify`, `orch fingerprint`, the no-proof notice, the board Proof column,
  archive-then-close, no reuse of proof workers. Plan review: 12 findings, fixed. Code review: 1
  round, 12 findings (Codex's safety filter stopped the reviewer, so the orch wrote the review from
  its repro script), all fixed; round 2 by owner choice was the orch's verification (repros
  NOT-REPRODUCED, proof, clean snapshot run, 2 mutation spot-checks), no re-review.
  Before that: plan `kis/intent/plan-2026-10-23-notice-fixes.md`, done, merged and released in 1.0.1 2026-10-23
  (spawn pointer + start confirmation and `not-started`; reused-pane resolution; turn-based notices
  with `completion_seq`, a 15 s debounce and Herdr-restart reset; session-scoped close of reused
  resources). 2 review rounds (11 findings, all fixed); round 3 verified by the orch with the
  reviewer's 11 repros, no third review.
  Earlier: plan `kis/intent/plan-2026-10-18-orch-v1.md` (v1, phases 1-6 and the 2026-10-20 board
  and close fixes) is done and merged. Caveats still open: the pre-release and board fix commits
  were not re-reviewed; `orch board` not seen live from a plain shell or an agent pane; `orch close`
  refuses a worktree holding only ignored `__pycache__` dirs unless `--discard` is passed.
- Blocker: none.
- Command: `env -u HERDR_ENV -u XDG_STATE_HOME HOME=$(mktemp -d) ./tests/run.sh` (314 tests,
  passing on the 1.1.0 tree, 2026-10-24; the PTY tests flake under heavy load, rerun one alone first).
- Proof: suites re-run by the orchestrator after every merge. Installer verified on 1.1.0
  (2026-10-24): `./bootstrap.sh update --source .` reported plugin 1.1.0, `check --source .` passed. Live
  (2026-10-19): hook, worker spawn and notice delivery; `orch adopt`; `./bootstrap.sh update --repo
  <github url>` refreshed the skill copy and `check` passed; `update` refuses to replace a local
  plugin link with a GitHub install.
- Live 2026-10-24 (Herdr 0.9.5, after the merge, throwaway Claude sonnet-5-5 build worker): a turn
  ending with no proof gave exactly one `stopped, no proof` notice; with proof, one `done`;
  `orch verify` passed (its clean run needed the untracked file, so the dirty tree was tested); after
  a tree edit verify failed on the fingerprint and the board went `passing` -> `present`; close
  refused the dirty file, then with `--discard` archived the proof and removed the worktree. Board
  Proof column looked at, at 160 columns. Not seen live: a review row's verify, the non-sequence
  path.
- Live 2026-10-23 (Herdr 0.9.5, after the merge): a Claude (sonnet-5-5) and a Codex (gpt-6-luna)
  worktree worker each submitted the pointer by themselves, got exactly one `done` notice, no early
  `idle`; both closed cleanly. 2026-10-23 later: the debounce path let a false `idle` through (a Claude
  worker stopped over 15 s mid-turn); Herdr-restart reset worked. Not yet seen live: the reused-pane
  close guard.
- Live 2026-10-22 (fresh Claude Code session, unregistered): `orch:model` researched, asked,
  and wrote the matrix file after approval; `orch:close` reached `orch list`, which
  answers "caller is not a registered orch".
- Not verified live: the other `orch:*` commands in a fresh Claude Code session, all of them in
  Codex, the cap on a real
  clock (`orch resume`, `[cap] prompts_per_hour`), `prefix+b` overlay closing on `q`, a GitHub plugin install,
  GitHub Actions, macOS and Bash 3.2. Duplicate notices are coalesced by a guard; the 2026-10-23
  probe found Herdr's false `done` blips and pane reuse (Knowledge), the likely causes. The school-next failed start was
  traced only to the stale pane ID (fixed).
- Cosmetic: history shows two author identities (`T <t@example.invalid>` and the owner). The
  pre-rewrite commits were already public; GitHub Support can purge cached views.
- Open defects (seen live 2026-10-23, still in 1.1.0): a Claude spawn typed the pointer but the
  retry Enter did not submit it (exit 1, `not-started`; a manual Enter worked); `orch list` shows
  `status`, so a `not-started` row reads `idle`; the 15 s debounce is too short for Claude mid-turn
  stops. New in idea 16: `orch spawn` writes the proof rules into the caller's brief file in place;
  `orch board` with redirected stdout opens the overlay instead of printing.
- Next: (0) owner picks the next cycle (the open defects above, or the idea list). (1) owner live
  checks above. (2)
  Parked: the herdrctx-style board (its review found a missing title lookup timeout, a fixed
  8-column Project, titles ignoring the session prefix, flat agent rows), row select-and-enter,
  the idea list. Owner decision 2026-10-19: no more builder/reviewer loops for now.
