# Plan: the orch repo and the four fixes (approved 2026-10-09)

Approved by the owner on 2026-10-09 in the tartib session that created this repo. Work mode:
Phase. One phase is proved and checked before the next begins (preference 21).

## Decisions (owner's words, 2026-10-09)

- Orch gets its own repo; session-close ships with it. The agent-memory skill gets a separate
  repo later, "that will work with Tartib in a way that anyone can attach any MCP for notes".
- "I want orch to work with and without KIS." So the ledger cannot live in `kis/state`.
- The ledger folder: no more sibling `<repo>.reports` at the top level; keep it in the repo,
  KIS-style. Resolution: `<repo>/.orch/`, excluded through `.git/info/exclude`, nothing committed.
- Advisor experiment: first "revert the advisor, keep the four named sub-agents, bring them into orch"; then, the same day, after the advisor caught four real defects in a review pass, "ok maybe we keep advisor if it's helping". Final: advisor kept, sub-agents kept and in orch.
- Usage: report only. The board and ledger show each CLI's remaining usage with reset times, and
  orch asks before starting a task on a CLI above 80% used. No automatic switching.
  Superseded later the same day (owner): "when choose agent the first rule is where usage
  available for the task then choose that, if not clear then ask user", and "claude can call
  codex or cmd and codex can call claude or cmd and cmd can call claude and codex". Orch 0.8.4
  chooses the kind by usage first, from any orchestrator kind, and asks only when no candidate
  is clearly available.
- Added mid-session (owner, 2026-10-09): orch's bootstrap must also set up Herdr, since orch
  depends on it (the binary and the Herdr agent skill). Independence is the rule for all
  three: KIS works alone; orch works with or without KIS; the memory skill, to be named
  `agent-memory`, works with or without KIS or orch.
- Added: rules for when to use a sub-agent, when a pane agent, and for a pane agent, when to
  create a worktree in a new Herdr workspace versus the same worktree in a new tab or pane.
- Added: the design workflow must split into a path without pen.dev and a path with it, and
  the way designs are presented for review needs to improve.
- Feedback that started this: agents get mixed up picking agent and model (Command Code was
  started with the wrong model); orch does not use KIS enough; orch watches context but not
  plan usage; the advisor is unused but named sub-agents proved useful.

## Scope

New repo `~/Repositores/side-projects/orch-skill`, shaped like kis-skill: `skills/orch`,
`skills/session-close`, bootstrap installer into `~/.agents/skills`, link
`~/.claude/commands/orch`, tests, its own `kis/`.

## Out of scope

- The agent-memory repo with a pluggable notes MCP (its own plan, later).
- Migrating the live tartib run (ledger at `../tartib.reports/orch`, owned by the Command Code
  orchestrator in pane w3:pH) to `.orch/`. A separate, owner-triggered step.
- Pushing to GitHub. Automatic CLI switching on usage.

## Phases

1. **Relocate.** Copy orch and session-close into the repo, move the research reports to
   `docs/research/`, write the installer and tests. Nothing behaves differently. Rollback: the
   backup `~/.agents/orch-backup-2026-10-07.tgz`.
   The installer also checks Herdr: `herdr` on PATH and the Herdr skill at
   `~/.agents/skills/herdr`; when missing it prints the official install commands
   (`curl -fsSL https://herdr.dev/install.sh | sh` or `brew install herdr`, plus the skill
   install) and runs them only with `--with-herdr`.
   Acceptance: installing from the repo into a temporary HOME yields `~/.agents/skills/orch`
   and `session-close` byte-identical to the source packages, and a valid
   `~/.claude/commands/orch` link; `check` reports current; a modified install is detected and
   `update` restores it. Installing over the real HOME leaves `~/.agents/skills/orch` equal to
   today's content except the research folder.
   **Done 2026-10-09 (orch 0.2.0 relocated, then 0.3.0+).** Proof: `tests/run.sh` install tests; the commands-link mutant failed the test and the original was restored by hash; live `bootstrap.sh check` current; Herdr skill refreshed from `herdr --skill`.
2. **Standalone.** Ledger, briefs, reports, handoffs, events.log, agents.txt, watcher.pid and
   wake.md move to `<repo>/.orch/` (`<repo>/.orch/<agent>/` per agent), added to
   `.git/info/exclude` by `start`. KIS, lessons (Tartib) and the project status space each
   become optional: when `kis/` or the Tartib MCP is absent, the step is skipped in one line.
   With KIS present: read State at start, and sync State after every merge and at handoff (the
   live ledger showed Next action saying "merge" after State and git said merged).
   `start` keeps its explicit dir argument so old runs are not disturbed.
   Acceptance: a fresh orchestrator in a temporary repo with neither `kis/` nor Tartib runs
   start, task (dry), status without error; in a repo with `kis/`, a merge event leaves State's
   Next equal to the ledger's.
   **Done 2026-10-09 (0.3.0).** Proof: orch-dir tests (fresh repo, shared exclude from a worktree, legacy detection with `--check` creating nothing, migrate, plain dir); walkthrough in a temp repo without `kis/`: ledger from template, `board` prints, `git status` clean; `orch-dir.sh --check` on tartib names the legacy run. Not proved: the KIS-present event path (State rewritten after a real merge).
3. **Runtime table.** One table per kind (claude, codex, cmd, agy): how to start it in a pane,
   how to prompt it, whether `herdr agent prompt` works, allowed and default models from
   preference 29 and the 2026-10-09 model thought, whether it can be an orchestrator and whether
   the sub-agent route exists (Claude only). After `agent start`, read the live model from
   `herdr agent list` (`display_agent`, `tokens.model`) and refuse on mismatch. Fix the 150k
   self-check to read the orchestrator's own pane by id (thought 382).
   Acceptance: starting cmd with a Claude model name is refused with the live model shown.
   **Done 2026-10-09 (0.4.0).** Proof: orch-model tests on fixtures (cmd from `tokens.model`, Claude and Codex from pane text, mismatch exit 1, not visible exit 2) and a live read-only check on a running cmd agent: deepseek passes, sonnet refused.
4. **Usage board.** Per CLI: 5-hour and 7-day used percentage and reset time on the board and in
   the ledger header, with the fetch time. Claude: the owner's `~/.claude/statusline-command.sh`
   also writes the `rate_limits` fields to a cache file. Codex: a one-call spike of the
   app-server `account/rateLimits/read` first (never called yet), then the collector. Command
   Code: "unknown" unless `CMD_API_KEY` is in the environment; the script never reads
   `auth.json` and never prints the key. Policy: report only; `task` asks before starting on a
   CLI above 80%.
   Acceptance: the board shows real, dated numbers for claude and codex.
   **Done 2026-10-09 (0.5.0, `check` refreshes since 0.6.1).** Proof: orch-usage tests including one live Codex app-server read (plan plus, 5h 23%, 7d 28% at the time); the statusline cache appeared at `~/.cache/orch/usage-claude.json` within minutes (5h 25%, 7d 88%).
5. **Placement rules and the sub-agent route.** One table in SKILL.md decides where work runs:
   sub-agent (one-message checks, research, short tasks that need no pane; Claude orchestrators
   only; dies with the orchestrator) versus pane agent (anything long, anything the user should
   watch, anything on another CLI); and for a pane agent, a new worktree in a new Herdr
   workspace (changes files on its own branch), the same worktree in a new tab (a second stream
   on the same branch that must not run at the same time as the first, such as review after
   build) or a new pane in the same tab (a helper the first agent and the user watch together,
   such as a dev server or a watcher). `/orch:task ... --sub worker|explorer|researcher|designer`
   implements the sub-agent route; the ledger's sub-agent table holds them and handoff lists
   running ones as lost.
   Acceptance: a `--sub` task returns a report and a ledger row; the table answers every case
   in the two run reports under `docs/research/` without a judgment call.
   **Done 2026-10-09 (0.6.0, worker isolation fixed in 0.6.1).** Text only. Not proved: the table against every case in the research reports; one real `--sub` run.
6. **Design workflow, two paths.** Interviewed 2026-10-09. Without pen.dev: ask the user to
   install it or to skip the design step for the task; nothing else is invented (no mockups, no
   wireframes). With pen.dev: the Pencil flow, with three JSON files beside the exports. Every
   round ends in two local HTML pages, never published unless the user is away and asks: a
   review page (only the changed screens, before and after, the user's feedback above each, a
   review-first list, answers by id in chat) and a prototype page that loads every exported
   frame and makes regions clickable so the whole app can be walked at once. Built by
   `scripts/design-pages.py`; method in `references/design.md`; the `designer` sub-agent points
   at both.
   Acceptance: from the real tartib exports, `check` is clean, both pages render headless and
   read correctly, and the hotspots sit where `links.json` says.
   **Done 2026-10-09 (0.7.0, `check --previous` in 0.7.1).** Proof: design-pages tests; both pages built from six real tartib exports, rendered headless and read by eye, hotspots drawn where `links.json` put them.

Independent fast task, done and then undone the same day: the advisor was reverted, then kept
at the owner's word. Settings are as before the revert; preference 27 says the advisor stays.

## Status

Complete 2026-10-09: all six phases done, orch at 0.7.1, session-close at 1.0.0.

Open acceptances, to prove in the first real run that uses this version:

- Phase 2: the KIS-present event path (State rewritten after a real merge).
- Phase 5: the placement table against every case in `docs/research/`.

Proved since: phase 5's real `--sub` run, 2026-10-09: a `worker` sub-agent with
`isolation: "worktree"` built the sub-agent shipping (0.8.0) in its own worktree; the
orchestrator verified it (suite, one mutation), committed b7fe302 there, merged, removed the
worktree.

Follow-up found in use: `scripts/orch-model.sh` reports a false MISMATCH for a fresh cmd agent
(Herdr has no `tokens.model` before its first turn, and the pane text drops the `deepseek/`
prefix); seen 2026-10-09 starting the lore agent.
Fixed in 0.8.2 (22c965e), with the installer now creating `~/.claude/skills/<name>` links.
Known limit: `bootstrap.sh update` does not repair a missing link for a skill already current.
