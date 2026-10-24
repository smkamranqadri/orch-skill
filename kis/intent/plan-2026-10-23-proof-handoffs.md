# Plan: proof-carrying handoffs and `orch verify` (idea 16)

Mode: Standard. Scope approved by the owner 2026-10-23. Source: idea 16 in
`ideas-from-0.12.2.md`; prototype in lore-skill `.orch/lore-2.0/{p1-common.md,review-common.md,verify.sh}`
(read it for intent only; it is lore-specific and its gaps are listed in the Review below).

## Owner decisions (2026-10-23)

1. Full idea as written, including gating `done` on proof.
2. A build or review worker whose turn ends without a proof block gets an immediate distinct
   notice `[orch] NAME stopped, no proof` (through the existing turn/debounce logic), not `done`.
3. Proof applies to roles `build` and `review` only; `plan` and `explore` are unchanged.
4. The test command comes from `orch spawn --test-cmd CMD` (required for `--role build`), stored
   on the row; the orch skill takes it from KIS State's Command line.
5. `orch verify` runs the clean test run itself as a subprocess with a log file, not in a pane.
6. No reuse for proof roles: a build or review worker does one task, is closed after merge, and a
   fresh one is spawned for the next task. `orch list --idle` never offers proof rows for reuse.
7. `orch close` archives the worker's proof directory to
   `~/.local/state/orch/proof/<session>/<name>/` (under `XDG_STATE_HOME` when set) before removing
   anything, and treats that directory as owned, not dirty.

## Definitions

- **Proof row:** a row created by `orch spawn --role build|review` after this change, marked with
  an additive field `proof: 1`. Rows without it (version-1 rows, adopted rows, plan/explore) keep
  today's behaviour everywhere: notices, verify (refuses: `FAIL no proof protocol on this row`),
  board (blank proof cell), close.
- **Proof dir:** `<row tree>/.orch/<name>/`, where `<row tree>` is the registered checkout root
  (the worktree for builders, the orch's tree for split-pane reviewers), resolved from the
  registry, never from a shell cwd. Spawn writes its absolute path into the brief.
- **Exclusion:** spawn resolves the exclude file with `git -C <row tree> rev-parse --git-path
  info/exclude` and appends the line `/.orch/` once: idempotent across spawns, preserving all
  existing bytes, adding a newline first if the file lacks a final one, creating it if missing.
- **Fingerprint:** one helper (in `orchlib`, also printed verbatim in `proof.md` as a command the
  worker runs, e.g. `orch fingerprint`) hashing, in a defined order: `HEAD` commit id, `git diff
  HEAD --binary`, then every non-ignored untracked path sorted bytewise, each with its file type,
  executable bit and content sha256 (symlinks hash their target string). Any git or read error is a
  failure, never an empty hash. Linux and macOS.
- **Snapshot:** for the clean run, verify builds a commit of the worker's current tree without
  touching its index, branch, stash or files: a temporary `GIT_INDEX_FILE` seeded from `HEAD`,
  `git add -A` into it, `write-tree`, `commit-tree` with parent `HEAD`; then `git worktree add
  --detach` of that commit into a temp dir.

## Scope

1. **Proof rules.** New `skills/orch/references/proof.md`, appended by `orch spawn` to the brief
   of every proof row (test command and absolute proof dir substituted); the pointer prompt stays
   one line.
   - Builder: after the last edit, the final run
     `{ <cmd> ; } > <proof dir>/run-<n>.log 2>&1; echo "exit=$?" >> <proof dir>/run-<n>.log`, then
     the fingerprint. `handoff.md` fields (last occurrence of each field wins; fix rounds append):
     `run_log`, `run_sha256`, `tree_fingerprint`, `mutations_log`, `guards` (comma-separated
     guard names, or `none`). `mutations.log` grammar, one record per line:
     `<guard> | <test file> | tripped=True|False | restored byte-identical=True|False`; any other
     nonblank line is malformed and fails verify; the latest record per guard decides.
   - Reviewer: in the proof dir, `review.md` with a `findings:` line (comma-separated IDs, or
     `none`) and an executable `repro.sh` taking an absolute checkout path as `$1`, run with that
     checkout as cwd, printing per finding `F<n> expected=... observed=...` then exactly one of
     `F<n> REPRODUCED|NOT-REPRODUCED|MANUAL`; exit 0; read-only on the checkout, temp data only,
     no model or network, under two minutes. The review brief names the builder's checkout path.
     Every non-MANUAL finding prints `REPRODUCED` against the reviewed tree before the review is
     written. A MANUAL finding needs a one-sentence reason in `review.md`.
2. **`orch spawn --test-cmd CMD`**: required with `--role build` (exit 2 with a clear error
   otherwise), optional for review, stored on the row with `proof: 1`.
3. **`orch verify NAME`**: prints only `PASS ...`, `FAIL ...`, `MANUAL ...` lines and a final
   `RESULT: PASS|FAIL (<n>)`; exit 1 on any FAIL. Holds the registry lock only to read the row
   and, at the end, to write the verdict; all git, test and repro work runs unlocked.
   - Build: handoff exists and has every field; log exists inside the proof dir; sha256 matches;
     last line exactly `exit=0`; fingerprint unchanged; `mutations.log` has no malformed record;
     every guard in `guards` has a latest record with `tripped=True` and
     `restored byte-identical=True` (a record for an undeclared guard also fails); then the clean
     run: the stored command via `/bin/sh -c`, cwd the snapshot root, log at
     `<proof dir>/verify-clean-<n>.log` (outside the snapshot), exit code captured; snapshot
     worktree removed and pruned on success, failure or interrupt.
   - Review: `orch verify NAME --against PATH [--want REPRODUCED|NOT-REPRODUCED]` (`--against`
     required, canonicalised; `--want` default `REPRODUCED`). Runs `repro.sh` with a 120 s timeout
     (child killed on timeout or interrupt). Fails on: nonzero exit, timeout, malformed result
     line, missing, duplicate or undeclared finding ID, missing evidence line, wrong verdict.
     MANUAL prints a `MANUAL` line and does not fail. `findings: none` with no result lines passes.
   - Verdict stored on the row: `passing|failing`, time, and a binding (proof-file digest, test
     command, fingerprint or `--against`+`--want`). It is written only if the row is still the
     same row (same name, not closed, same spawn time) and its proof digest still matches;
     otherwise verify prints `FAIL row changed during verify` and writes nothing.
4. **Notices.** For proof rows, at both places the hook queues a terminal notice today (the
   rising-completion path and the debounced path), a bounded presence check decides `done` vs
   `stopped, no proof`: build needs a regular `handoff.md` (read at most 64 KiB) containing every
   field; review needs a regular `review.md` with a `findings:` line and an executable regular
   `repro.sh`. Unreadable, oversized, non-regular or malformed counts as missing. No hashing, git
   or subprocesses. Turn bookkeeping, `blocked`, `closed`, legacy rows unchanged; still one notice
   per turn.
5. **Board.** A `Proof` column after Status for agent rows: `missing`, `present` (proof exists,
   no verdict or verdict binding no longer matches), `failing`, `passing`; blank for plan,
   explore and legacy rows and for orch rows. The proof state is computed at render time, so it
   refreshes without a registry change. Layout keeps Name/Status/Project/Title readable at the
   supported widths; Title shrinks first.
6. **Close.** For proof rows, close copies the proof dir to the archive path (decision 7) before
   any removal and fails without removing anything if the copy fails; the worktree-dirty check
   ignores only that row's `.orch/<name>/` (any other ignored or dirty file still refuses without
   `--discard`). For split-pane reviewers the proof dir in the orch's tree is removed after the
   archive. `orch list --idle` excludes proof rows (decision 6).
7. **Docs.** `skills/orch/SKILL.md` (CLI lines for `--test-cmd`, `verify`, fingerprint; proof
   roles are not reused; the clean run is the one exception to "test runs in a plain pane"),
   `skills/orch/commands/act.md` (brief with `--test-cmd` and the builder checkout for reviewers;
   on notice run `orch verify` as one background job, then review, verify the review with
   `--against`, fix round re-verified with `--want NOT-REPRODUCED`, merge, close), README.

## Out of scope

Suite counting; ideas 2-14; a release (separate, after the live check); changing 1.0.1's turn
and debounce logic beyond inserting the proof check; reuse of proof workers.

## Acceptance

- Suite: `env -u HERDR_ENV -u XDG_STATE_HOME HOME=$(mktemp -d) ./tests/run.sh` passes.
- Verify, each with an anchored FAIL line: missing handoff; each missing field; missing log; hash
  mismatch; last line not `exit=0`; fingerprint change from each of a new commit, staged edit,
  unstaged edit, added file, deleted file, binary change, mode change, symlink change; malformed
  or truncated latest mutation record; a declared guard with no record; latest record
  `tripped=False` or `restored byte-identical=False` (both append orders); a passing base whose
  uncommitted change fails tests (clean run must test the dirty tree), with the worker's index,
  branch, stash and files byte-identical afterwards; repro nonzero exit, timeout, missing,
  duplicate, undeclared ID, wrong verdict. Passes: correct build fixture, correct review fixture,
  `findings: none`, MANUAL present.
- Lock: a slow verify does not block another registry command; close or name reuse during verify
  writes no verdict to the replacement row.
- Hook: proof build and review rows with and without proof, through both terminal paths: exactly
  one notice of the right kind; a false blip still yields none; explore and legacy rows notify
  `done` without proof; the existing lock-latency test covers the proof check.
- Exclusion: main checkout and linked worktree, repeated spawn, missing file, unterminated last
  line; proof files never enter the fingerprint.
- Close: verify, merge and close a proof worker with no `--discard`; archive present and
  byte-identical; an unrelated ignored file still refuses.
- Board: exact fixtures for the four proof states and blank rows at 55, 67, 100 and 160 columns.
- Every new guard is mutation-checked (literal edit, named test fails, restored byte-identical).
- Live in Herdr: a build worker without proof gets the no-proof notice; with proof, `done`, and
  `orch verify` passes; the board shows the proof column (looked at, not just tested). Merging to
  `main` changes the live plugin, so the owner approves the merge.

## Files likely involved

`plugin/orchlib.py`, `plugin/hook.py`, `plugin/board.py`, `plugin/orch`,
`skills/orch/references/proof.md` (new), `skills/orch/SKILL.md`, `skills/orch/commands/act.md`,
`README.md`, `tests/test_phase*.py`, `tests/test_board.py`, fixtures.

## Risks

- A worker that writes proof early then keeps editing: verify catches it (fingerprint); the hook
  only sees existence. Accepted.
- Clean-run duration: the orch runs `orch verify` as one background job.
- Large diff for one builder and at most 2 review rounds: the builder self-checks against the
  acceptance list before handing off.

## Agents (owner-approved 2026-10-23)

Plan review: Codex gpt-6.1-sol high, split pane, read-only. Build: Claude Code claude-sonnet-5-5
medium, worktree. Code review: Codex gpt-6.1-sol xhigh, split pane, read-only, at most 2 rounds.

## Review
- Reviewed: 2026-10-23 by codex gpt-6.1-sol (high); plan hash 5868f0fc5807
- [fixed] P01 fingerprint omits HEAD, modes, symlinks - Definitions: Fingerprint; acceptance per change kind.
- [fixed] P02 clean run tests HEAD, not the dirty tree - Definitions: Snapshot; Scope 3 shell, cwd, log, cleanup; dirty-tree acceptance; skill exception documented.
- [fixed] P03 repro output not checked against a finding set - review.md `findings:`; missing, duplicate, undeclared, exit, timeout fail; MANUAL and none defined.
- [fixed] P04 omitted or malformed guard records pass - `guards` field, record grammar, latest-record rule, fixtures.
- [fixed] P05 verify under the registry lock - short lock scopes; verdict written only to the same row.
- [fixed] P06 reviewer cwd vs reviewed checkout - proof dir from the registered tree; `--against` required; brief names the builder checkout.
- [fixed] P07 close refuses ignored .orch and would delete proof - owner decision 7: archive then close; Scope 6.
- [fixed] P08 role-only gate breaks legacy and adopted rows - `proof: 1` marker; legacy behaviour defined.
- [fixed] P09 reuse and stale verdicts - owner decision 6: no reuse for proof roles; verdict binding.
- [fixed] P10 literal .git/info/exclude fails in worktrees - `rev-parse --git-path`, idempotent append, fixtures.
- [fixed] P11 unbounded proof read in the hook, paths untested - bounded regular-file check; both terminal paths and review rows tested.
- [fixed] P12 board layout undefined - Proof column, render-time state, fixtures at four widths, live look.
