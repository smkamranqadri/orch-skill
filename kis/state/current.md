# Current

- Branch: `main`, no remote. Nothing pushed anywhere.
- Task: Phase 2 of `../intent/plan-2026-10-09-orch-repo.md` (standalone `.orch/`, optional
  KIS, lessons and status space, State sync after merges), on top of Phase 1 (done).
- Status: Phase 2 **done** 2026-10-09 and installed live (orch 0.3.0). `scripts/orch-dir.sh`
  picks the run dir: `<repo>/.orch/` excluded via `.git/info/exclude`, resolved to the main
  checkout from a worktree, legacy `../<repo>.reports/orch/` kept while it exists, `--migrate`
  moves it. SKILL.md has a "Works alone" table (KIS, lessons space, status space optional);
  commands skip each absent one in one line; `event` rewrites State after a merge when `kis/`
  exists. Phase 1 (relocation, installer, Herdr doctor) done earlier the same day.
- Command: `tests/run.sh`; `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof (2026-10-09): `tests/run.sh` passes (install tests and orch-dir tests: fresh repo,
  shared exclude from a worktree, legacy detection with --check creating nothing, migrate,
  plain dir). Walkthrough in a temp repo without `kis/`: orch-dir, ledger from template,
  `board` prints, `git status` clean. `orch-dir.sh --check` on tartib names the legacy run and
  creates nothing. Live: `bootstrap.sh check --source .` current. Phase 1 proof: commands-link
  mutant failed the test and was restored by hash.
- Done today besides: advisor experiment reverted (settings keys removed, backup
  `~/.claude/settings.json.bak-2026-10-09`; preference 27 rewritten; ai-lab note 335 annotated).
- Next: Phase 3, the runtime table per kind (claude, codex, cmd, agy) with a live-model
  assertion after start, and the 150k self-check fix (already worded in SKILL.md).
  The tartib run still uses its legacy ledger; migrate only at the owner's word.
