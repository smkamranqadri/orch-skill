# Current

- Branch: `main`, no remote. Nothing pushed anywhere.
- Task: Phase 3 of `../intent/plan-2026-10-09-orch-repo.md` (runtime table and live-model
  check), on top of Phases 1 and 2 (done).
- Status: Phase 3 **done** 2026-10-09 and installed live (orch 0.4.0): `references/runtimes.md`
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
- Proof (2026-10-09): `tests/run.sh` passes (install, orch-dir and orch-model tests; the
  model tests include a live read-only check against a running cmd agent: deepseek passes,
  sonnet is refused). Earlier the same day: install and orch-dir tests: fresh repo,
  shared exclude from a worktree, legacy detection with --check creating nothing, migrate,
  plain dir). Walkthrough in a temp repo without `kis/`: orch-dir, ledger from template,
  `board` prints, `git status` clean. `orch-dir.sh --check` on tartib names the legacy run and
  creates nothing. Live: `bootstrap.sh check --source .` current. Phase 1 proof: commands-link
  mutant failed the test and was restored by hash.
- Done today besides: advisor experiment reverted (settings keys removed, backup
  `~/.claude/settings.json.bak-2026-10-09`; preference 27 rewritten; ai-lab note 335 annotated).
- Next: Phase 4, the usage board: Claude from the statusline JSON (edit the owner's
  `~/.claude/statusline-command.sh` to also write a cache file), Codex after a one-call spike
  of `account/rateLimits/read`, cmd "unknown" without `CMD_API_KEY`; report only, ask above
  80%. The tartib run still uses its legacy ledger; migrate only at the owner's word.
