# Current

- Branch: `main`, no remote. Nothing pushed anywhere.
- Task: Phase 4 of `../intent/plan-2026-10-09-orch-repo.md` (usage board), on top of Phases
  1 to 3 (done).
- Status: Phase 4 **done** 2026-10-09 and installed live (orch 0.5.0): `scripts/orch-usage.py`
  (claude from the statusline cache the owner's `~/.claude/statusline-command.sh` now writes
  to `~/.cache/orch/usage-claude.json`, backup `.bak-2026-10-09`; codex over the app-server
  `account/rateLimits/read`, spiked live: plan plus, 5h 23%, 7d 28%; cmd unknown without
  `CMD_API_KEY`, endpoint unverified). The watcher shows the usage line every 5 minutes, the
  ledger header carries it, `task` asks before starting on a CLI at or above 80%.
  Phase 3 **done** earlier (orch 0.4.0): `references/runtimes.md`
  (claude, codex, cmd, agy: start, prompt, live model, default/allowed/avoid models, from
  preference 29 and the 2026-10-09 model thought) and `scripts/orch-model.sh`, which `task`
  runs after every start and before the first prompt (cmd from `tokens.model` in the agent
  list; Claude and Codex from pane text, which is the only place they show it).
  Phase 2 **done** earlier the same day (orch 0.3.0). `scripts/orch-dir.sh`
  picks the run dir: `<repo>/.orch/` excluded via `.git/info/exclude`, resolved to the main
  checkout from a worktree, legacy `../<repo>.reports/orch/` kept while it exists, `--migrate`
  moves it. SKILL.md has a "Works alone" table (KIS, lessons space, status space optional);
  commands skip each absent one in one line; `event` rewrites State after a merge when `kis/`
  exists. Phase 1 (relocation, installer, Herdr doctor) done earlier the same day.
- Command: `tests/run.sh`; `./bootstrap.sh check --source .`; `./bootstrap.sh doctor`.
- Blocker: none.
- Proof (2026-10-09): `tests/run.sh` passes (install, orch-dir, orch-model and orch-usage
  tests; the usage tests include one live Codex app-server read, which answered; the
  model tests include a live read-only check against a running cmd agent: deepseek passes,
  sonnet is refused). Earlier the same day: install and orch-dir tests: fresh repo,
  shared exclude from a worktree, legacy detection with --check creating nothing, migrate,
  plain dir). Walkthrough in a temp repo without `kis/`: orch-dir, ledger from template,
  `board` prints, `git status` clean. `orch-dir.sh --check` on tartib names the legacy run and
  creates nothing. Live: `bootstrap.sh check --source .` current. Phase 1 proof: commands-link
  mutant failed the test and was restored by hash.
- Done today besides: advisor experiment reverted (settings keys removed, backup
  `~/.claude/settings.json.bak-2026-10-09`; preference 27 rewritten; ai-lab note 335 annotated).
- Next: Phase 5, placement rules (sub-agent vs pane agent; new worktree in a new workspace vs
  same worktree in a new tab or pane) and the `--sub` route. Then Phase 6, the design workflow
  in two paths, which starts with a short interview. The tartib run still uses its legacy
  ledger; migrate only at the owner's word. The Claude usage cache appears once a Claude
  session's statusline runs after this change.
