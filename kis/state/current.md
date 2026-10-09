# Current

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public, like kis-skill). Pushed 2026-10-09 through edf5105; 22c965e and this sync are local.
- Task: none in progress. The plan `../intent/plan-2026-10-09-orch-repo.md` is complete:
  six phases done on 2026-10-09, orch at 0.8.4 (0.8.2 cmd model check and skill links; 0.8.3 Command Code model roles; 0.8.4 usage-first kind choice, any kind starts any kind), session-close at 1.0.1, both installed live
  from this repo (`bootstrap.sh check --source .` current).
- Command: `tests/run.sh` (eight test files, all pass as of 22c965e);
  `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof: per phase under its entry in the plan file. 0.8.0 (b7fe302): suite pass, the
  never-clobber guard mutation-checked. 0.8.1 (0a285d4): suite pass (seven files), the
  no-agent-lessons guard mutation-checked. 0.8.2 (22c965e): suite pass, 16 mutations by the
  Codex worker plus the full-model boundary re-mutated by the orchestrator; live `check` current,
  four agents and both skill links current; live `orch-model.sh lore deepseek/deepseek-v4-flash`
  exit 0.
- Not proved: two open acceptances, listed under Status in the plan file.
- Next: lore (`../lore-skill`, plan `../lore-skill/kis/intent/plan-2026-10-09-lore.md`)
  replaced agent-lessons on 2026-10-09; its phase 3 onward runs there. Then the tartib run's migration to `.orch/` at the owner's word.
