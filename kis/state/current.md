# Current

- Branch: `main`, no remote. Nothing pushed anywhere.
- Task: Phase 1 of `../intent/plan-2026-10-09-orch-repo.md` (relocate orch and session-close
  into this repo with an installer, Herdr doctor and tests).
- Status: Phase 1 **done** 2026-10-09, committed (`818138f` plus a fix commit), and the live
  install now comes from this repo: `bootstrap.sh update --source . --with-herdr` replaced
  `~/.agents/skills/orch` (backup `~/.agents/orch-backup-20261009-143035.tgz`), left
  session-close as is, and refreshed the stale Herdr skill from `herdr --skill`.
  `bootstrap.sh check --source .` reports every skill current and the Herdr doctor clean.
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
- Next: Phase 2 (standalone `.orch/`, optional
  KIS, lessons and status space). Independent fast task still open: revert the advisor
  experiment (settings keys, preference 27 and 28 text, ai-lab note 335).
