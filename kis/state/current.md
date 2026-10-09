# Current

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public, like kis-skill). Pushed 2026-10-09 through 0a285d4 and the KIS sync after it.
- Task: none in progress. The plan `../intent/plan-2026-10-09-orch-repo.md` is complete:
  six phases done on 2026-10-09, orch at 0.8.1, session-close at 1.0.1 (both point at lore, 0a285d4; sub-agents shipped in 0.8.0), both installed live
  from this repo (`bootstrap.sh check --source .` current).
- Command: `tests/run.sh` (seven test files, all pass as of 0a285d4);
  `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof: per phase under its entry in the plan file. 0.8.0 (b7fe302): suite pass, the
  never-clobber guard mutation-checked. 0.8.1 (0a285d4): suite pass (seven files), the
  no-agent-lessons guard mutation-checked; live `bootstrap.sh check --source .` current, four
  agents current.
- Not proved: two open acceptances, listed under Status in the plan file.
- Next: lore (`../lore-skill`, plan `../lore-skill/kis/intent/plan-2026-10-09-lore.md`)
  replaced agent-lessons on 2026-10-09; its phase 3 onward runs there. Then the tartib run's migration to `.orch/` at the owner's word.
