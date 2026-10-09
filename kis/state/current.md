# Current

- Branch: `main`, new repo, **no commits yet**, no remote. Nothing pushed anywhere.
- Task: Phase 1 of `../intent/plan-2026-10-09-orch-repo.md` (relocate orch and session-close
  into this repo with an installer, Herdr doctor and tests).
- Status: Phase 1 built and proved on 2026-10-09; waiting on the owner's word to commit.
  The live install under `~/.agents/skills` is unchanged and still the working copy;
  `bootstrap.sh check --source .` against the real HOME reports orch differs only by the
  `research/` folder (moved to `docs/research/` here) and session-close identical.
- Command: `tests/run.sh`; `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof (2026-10-09):
  - `tests/run.sh`: install tests pass (install, byte-identical diff, refuse without --force,
    check current, drift detected, update restores with backup, --only, --no-claude-link,
    real directory refused, Herdr doctor exit 1 then pass after --with-herdr, install runs the
    Herdr check).
  - Mutation: removing the `ln -s` for the commands link makes the test fail at
    "commands link missing"; original restored (sha matches) and green again.
  - Live comparison: only `research` differs for orch; session-close identical.
- Finding: the Herdr skill at `~/.agents/skills/herdr` (installed 2026-09-25) differs from the
  copy bundled in herdr 0.9.3 (`herdr --skill`); `bootstrap.sh doctor --with-herdr` would
  refresh it, not run.
- Next: owner commits Phase 1; call the advisor; then Phase 2 (standalone `.orch/`, optional
  KIS, lessons and status space). Independent fast task still open: revert the advisor
  experiment (settings keys, preference 27 and 28 text, ai-lab note 335).
