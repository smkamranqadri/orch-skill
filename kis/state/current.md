# Current

- Branch: `main`, no remote. Nothing pushed anywhere.
- Task: Phase 6 of `../intent/plan-2026-10-09-orch-repo.md` (design workflow, two paths), on
  top of Phases 1 to 5 (done).
- Status: Phase 6 **done** 2026-10-09 and installed live (orch 0.7.0): `references/design.md`
  (pen.dev present: Pencil flow plus inventory, links and review JSON; absent: ask to install
  or skip) and `scripts/design-pages.py` (local `review.html` and `prototype.html` with
  clickable regions; `check` for missing images, dangling links, off-frame rects). The
  `designer` sub-agent points at both.
  Phase 5 **done** earlier (orch 0.6.0): `references/placement.md`
  (sub-agent; pane agent in a new worktree and workspace; new tab on the same worktree; helper
  pane; replacement; successor) with the Herdr commands for each, and `task` gained `--place`
  and `--sub` (the four named sub-agents, Claude orchestrators only, ledger Sub-agents table,
  lost at handoff). Text only, no script. **Not proved**: the plan's acceptance (every case in
  the two research reports answered by the table without a judgment call) was not walked; the
  `--sub` route has not been run once. Also not proved: Phase 2's KIS-present event path (State
  rewritten after a merge), which only a real merge event in a run can show.
  Phase 4 **done** earlier (orch 0.5.0): `scripts/orch-usage.py`
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
- Proof (2026-10-09): `tests/run.sh` passes (install, orch-dir, orch-model, orch-usage and
  design-pages tests). Phase 6 looked at: both pages built from six real tartib exports,
  rendered with headless Chrome and read by eye (before/after, feedback block, review-first
  link, frame list, a phone frame with its hotspots drawn where links.json put them). Earlier
  (orch-usage tests; the usage tests include one live Codex app-server read, which answered; the
  model tests include a live read-only check against a running cmd agent: deepseek passes,
  sonnet is refused). Earlier the same day: install and orch-dir tests: fresh repo,
  shared exclude from a worktree, legacy detection with --check creating nothing, migrate,
  plain dir). Walkthrough in a temp repo without `kis/`: orch-dir, ledger from template,
  `board` prints, `git status` clean. `orch-dir.sh --check` on tartib names the legacy run and
  creates nothing. Live: `bootstrap.sh check --source .` current. Phase 1 proof: commands-link
  mutant failed the test and was restored by hash.
- Done today besides: the advisor experiment was reverted and then kept again at the owner's
  word (it caught four real defects in the Phase 5 review); `~/.claude/settings.json` holds
  `advisorModel` and `effortLevel` as before, preference 27 says it stays, ai-lab note 335 has
  both thoughts.
- 0.6.1 (review fixes): `orch-usage.py check` refreshes before deciding (a fresh orchestrator
  could otherwise start on a CLI at 88% with exit 2); `--sub worker` uses the Agent tool's
  `isolation: "worktree"`; `references/brief-rules.md` ships the standing rules so briefs stand
  without a lessons space; SKILL.md no longer names the installer.
- Next: the agent-memory repo (its own plan: the lessons skill with a pluggable notes
  backend). Also open: the three unproved items above, and the tartib run's legacy ledger
  (migrate only at the owner's word). The tartib run still uses its legacy
  ledger; migrate only at the owner's word. The Claude usage cache appears once a Claude
  session's statusline runs after this change.
