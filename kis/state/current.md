# Current

- Branch: `main` at ab56aae, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public). Pushed through 3432eab (orch 0.9.0); be5bf15..ab56aae (0.9.1, 0.10.0 and their docs)
  are local only.
- Task: none in progress. The plan `../intent/plan-2026-10-13-visibility.md` (ideas from
  herdr-dagr: `mark` evidence tiers and attempts, the board's EVID column and Needs-you block,
  `check`, `show`, `stats`) is merged as orch 0.10.0 (ff to ab56aae, 2026-10-14), installed live
  (`bootstrap.sh check --source .` exit 0), and the live watcher restarted on it (pane wG:p2,
  pid 64982). orch 0.9.1 (be5bf15, ctx-trims' orch part: `scripts/orch-agents.sh` replaces raw
  Herdr list reads) merged and installed 2026-10-13; its kis-skill part stays with w3:pZ.
  Orchestrator of this run since 2026-10-13: orch-5 (Claude Opus, wG:p6); orch-4 (wG:p5) idle.
- Command: `tests/run.sh` (13 test files; `ORCH_TEST_NO_LIVE=1` skips the live Codex probe);
  `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`;
  `python3 ~/.agents/skills/orch/scripts/orch-watch.py check .orch --owner <pane>`.
- Blocker: none.
- Proof (0.10.0): the builder's clean detached suite and 50 of 50 mutants killed
  (`.orch/visibility/report.md`). orch-5 re-ran the full suite in a clean detached checkout at
  ab56aae (13 files pass, 48 new unittest cases) and killed three more mutants (move resetting
  attempts, `open` hold-off, ledger limit; originals restored, cmp identical); logs in
  `.orch/visibility/proof/`. Live, read-only on the real run dir (md5 unchanged): `check` named
  the three done-not-closed agents, 79 > 60 ledger lines, the stale Watcher line and 7
  unparseable log lines; the board's Needs-you block listed them. The restarted watcher draws
  the EVID column and shows `mark` lines in Recent.
- Proof (0.9.1): clean detached suite (12 files) pass; two mutants killed (raw-list guard,
  not-live exit 2).
- Not proved: a real multi-agent run using marks end to end; a real multi-owner run and a
  successor wake by owner. A watcher restart resets finish ages, so old finishes reach Needs you
  10 minutes after a restart (follow-up). Cache freshness is the write time; the mod keeps its
  last reading after a failed fetch. Prior plan `../intent/plan-2026-10-09-orch-repo.md` keeps
  one open acceptance (the placement table against research cases).
- Next: before pushing, the owner decides on `tests/fixtures/visibility/` (a copy of this run's
  real ledger and events.log, with the owner's quoted decisions; no secrets or home paths) for a
  public repo. Then push main. Full-permission agent starts stay held (brief
  `.orch/yolo/brief-full-permissions.md`; the owner applies it). Tartib run migration stays parked.
