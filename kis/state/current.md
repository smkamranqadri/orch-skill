# Current

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/orch-skill`
  (public). Pushed through 8029872; f5ea953, 2465eb0 (orch 0.9.0) and this sync are local.
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
- Not proved: a real multi-owner run and a successor wake by owner; a real cmd statusline write
  into `~/.cache/orch/usage-cmd.json` (needs a live cmd repaint). Cache freshness is the write
  time; the mod keeps its last reading after a failed fetch. Prior plan
  `../intent/plan-2026-10-09-orch-repo.md` keeps two open acceptances (the KIS-present merge
  event, first exercised by this merge; the placement table against research cases).
- Next: full-permission agent starts are approved by the owner in words but held: Claude Code's
  auto-mode check refused relaying them to a worker ([Create Unsafe Agents]); the owner applies it
  (permission rule, or directly in a pane), brief `.orch/yolo/brief-full-permissions.md`. Push
  orch-skill at the owner's word. Tartib run migration stays parked.
