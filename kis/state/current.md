# Current

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public). Pushed through 3432eab (orch 0.9.0); later session-close syncs pushed with them.
- Task: none in progress. The plan `../intent/plan-2026-10-09-multi-orch.md` (one watcher, many
  orchestrators; readable watcher pane; cmd usage from its statusline) is merged as orch 0.9.0
  (fast-forward to 2465eb0, 2026-10-09), installed live (`bootstrap.sh check --source .` current,
  exit 0), and the live watcher restarted on it (pane wG:p2).
- Command: `tests/run.sh` (ten test files; `ORCH_TEST_NO_LIVE=1` skips the live Codex probe);
  `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof: worker suite and 14 mutations (`.orch/orchwatch/handoff.md`, logs in
  `.orch/orchwatch/proof/`). The orchestrator re-ran the full suite in a clean detached checkout
  at 2465eb0 (all ten files pass, 15 new unittest cases) and killed one more mutant (move without
  the owner check: test_move and test_cli_registration fail; original restored, cmp identical).
  Live: restarted watcher shows one board in its scrollback (header count 1), owner column, five
  Recent lines. The cmd block is in `~/.commandcode/statusline.sh` (backup
  `statusline.sh.bak-2026-10-09-orch`); a sample payload through it wrote `usage-cmd.json` and
  `orch-usage.py check cmd` read `40% used`.
- Live cmd usage proved 2026-10-09 20:53: a live cmd repaint wrote `~/.cache/orch/usage-cmd.json`
  and `orch-usage.py check cmd` read `77% used`.
- Not proved: a real multi-owner run and a successor wake by owner. Cache freshness is the write
  time; the mod keeps its last reading after a failed fetch. Prior plan
  `../intent/plan-2026-10-09-orch-repo.md` keeps one open acceptance (the placement table against
  research cases); its KIS-present merge event was proved by this merge.
- Next: full-permission agent starts are approved by the owner in words but held: Claude Code's
  auto-mode check refused relaying them to a worker ([Create Unsafe Agents]); the owner applies it
  (permission rule, or directly in a pane), brief `.orch/yolo/brief-full-permissions.md`. Tartib run migration stays parked.
