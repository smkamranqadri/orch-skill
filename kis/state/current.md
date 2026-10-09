# Current

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public, like kis-skill). Pushed 2026-10-09.
- Task: none in progress. The plan `../intent/plan-2026-10-09-orch-repo.md` is complete:
  six phases done on 2026-10-09, orch at 0.7.1, session-close at 1.0.0, both installed live
  from this repo (`bootstrap.sh check --source .` current).
- Command: `tests/run.sh` (five test files, all pass as of the last commit);
  `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof: per phase under its entry in the plan file. Last full run of `tests/run.sh` on
  2026-10-09 after 0.7.1: install, orch-dir, orch-model, orch-usage, design-pages all pass.
- Not proved (plan acceptances still open): the placement table against every case in
  `docs/research/`; one real `--sub` run; the KIS-present event path (State rewritten after a
  real merge). Prove them in the first real run that uses this version.
- Next: the agent-memory repo, its own plan (the lessons skill with a pluggable notes backend,
  Tartib as the default mapping; works with or without KIS or orch). Then the tartib run's
  migration to `.orch/` at the owner's word.
