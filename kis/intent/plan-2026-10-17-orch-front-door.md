# Plan: orch as the global front door (path B, after lore 1.0.0)

Status: APPROVED 2026-10-17 by the owner; not started. Phase mode. Current status and proof live in State.

Goal: one global pair, `orch:start` and `orch:close`, usable in any repo on Claude Code, Codex,
Command Code (cmd) and agy, with the same layer on each. KIS stays the project memory when a repo
has `kis/`; orch's multi-agent machinery loads only in Agents mode. Cut tokens and ceremony before
the first useful action (research bar: 70%, reported), with no rise in forgotten work or recovery
failures (gated).

Repos: `orch-skill` (orch, session-close, installer) and `../kis-loop-skill` (KIS source, vendored
into `orch-skill/.agents/skills/kis`).

Reviewed 2026-10-17 by Codex gpt-6.1-sol (high, read-only): verdict rework, 1 blocker + 11 major +
1 minor; all folded in below (finding numbers in brackets). Second pass the same day: ready after
fixes, 10 major + 1 minor, folded in as [2.n].

## Decisions (owner, 2026-10-16/17)

1. Front door: `orch:start` everywhere. With `kis/` it runs KIS's start step, reusing KIS's mode
   pick and its single confirmation (no second mode question) and adds one mode, Agents. Without
   `kis/` it offers to install KIS or runs on the ledger alone. Herdr is required only in Agents
   mode [11]. `kis:start` keeps working standalone. KIS stays installed per repo: `orch:start`
   reads the repo's vendored KIS version and, below 0.11.0, offers that repo's one-line KIS update,
   continuing on the old version if declined [2.3].
2. `orch:close` is the single close: closes agents when a run is active, KIS sync + check when
   `kis/` exists, cleans merged worktrees and branches, commits and pushes. session-close retires
   with no alias: the installer removes its links and its installed package
   (`~/.agents/skills/session-close`), keeping modified or foreign content and saying so [5].
3. Substrate stays Herdr. The watcher already reads Herdr's `agent_status` and `completion_seq`
   (`orch-watch.py:454`) [10]; phase 3 audits it by function and real use, then proposes cuts with
   measured savings before any code changes.
4. During a run the ledger is the live record; KIS State holds the pointer line ("orch run active:
   ledger at <path>") plus one proof line per merge. Every State writer (KIS sync, orch handoff,
   orch close) recognizes the pointer; decisions flush to Intent at close (handoff passes them on
   in its packet) [4]. KIS's recovery contract (SKILL.md, `start`, `check`) accepts and follows an
   active-run pointer [2.6]. Without KIS, ordinary sessions use a minimal ledger (task, next action,
   decisions, done; no pane, owner or watcher fields) that loads outside Agents mode and that
   `check` accepts without a watcher [2.4].
5. KIS gains a State stamp (`Stamp: <branch> <short sha>`, written by sync) that the SessionStart
   anchor compares with the live repo; the comparison ignores commits that touch only `kis/`, so the
   commit recording a sync never makes State stale while later code commits do [2.5]. PreCompact
   hook dropped: its output never reaches the model
   on Claude or Codex [1]. Stop gate and Stop sync reminder: not now.
6. Plan review lives in KIS: the rule goes into KIS's SKILL.md (authoritative); `kis:plan` runs a
   cross-CLI review of the written plan (reviewer CLI differs from the author's; harness, model and
   effort proposed for approval) and records what was reviewed (a hash of the plan with its
   designated progress fields, such as Status and task checkboxes, excluded [2.8]) and the
   findings' outcome; `kis:act` refuses to start when the plan has no recorded review or changed after it
   [7]. orch without KIS applies the same rule to the agent's in-reply plan.
7. orch gains a split gate and a cross-CLI diff review before merge. The ledger records per task
   its dependencies and owned paths; `orch:task` compares against every active task, runs ordered
   or overlapping work sequentially, and releases it when the blocker merges [8]. A held task is a
   ledger row with status `queued: after <task>`, which parsing and `check` accept without a watcher
   registration [2.9].
8. Install: `bootstrap.sh` (same pattern as lore). `npx skills add` when public. Plugin only if hook
   wiring proves painful.
9. Remove every `/lore:load`, `/lore:retro` step and lore rule-number citation (lore 1.0.0 loads and
   captures on its own).
10. Measure first: a baseline before changes, the same probe at the end. 70% is reported; the gate
    is no rise in forgotten work, recovery failures, or approval and setup interactions [9].
    Forgotten work is measured: each case seeds a known inventory of unfinished work and decisions;
    any entry missing after recovery is a failure [2.10].
11. Legacy run folders `../<repo>.reports/` (example-app 2.4 GB, tartib 11 MB, anjuman 48 KB) migrate
    to `<repo>/.orch/` or KIS with references repaired, inside the ledger and in every KIS file or
    kept artifact that cites them [2.2]; the legacy path is removed after; deletion only on the
    owner's yes per folder [6].
12. Old orch backlog moves to an Intent backlog now; re-triaged in phase 5.

## Out of scope

KIS Stop gate; PreCompact hooks; plugins and npx publishing; vendoring the new KIS into repos other
than orch-skill; lore changes; agent-of-empires; trimming KIS start beyond what decision 1 needs.

## Test home and gates (all phases) [12][13]

- Phases 0–4 run against an isolated test home (`HOME=<scratch>/home`, pinned packages: orch
  0.10.0, session-close 1.0.2, KIS 0.10.1 for the baseline; each changed package installed there
  before its live acceptance, hook wiring refreshed, loaded versions and paths printed). The owner's
  real home is updated only in phase 5.
- Gates: orch-skill `tests/run.sh`; kis-loop-skill its validator and its six test scripts per its
  AGENTS.md, plus `ACTIVE_VERSION`, SKILL metadata and tag agreement for a release. Every new guard
  mutation-checked.

## Phases

### Phase 0: baseline
- `scripts/measure-start.sh` (source clone only): static part lists the files each path loads
  (`kis:start`, `orch:start` light and heavy, `session-close`) plus each host's global file chain,
  with words and estimated tokens (words x 1.3), labelled as estimates.
- Live part, separately labelled: a fixed set of three cases (small fix in a KIS repo, resume after
  `/clear`, start in a repo without KIS), run once per host in the test home from identical, reset
  fixtures: tokens before the first useful action from transcript usage fields (Claude, Codex; cmd
  and agy marked "no usage field" if absent), number of approvals and setup interactions, and the
  recovery check: each fixture seeds a known inventory of unfinished work and decisions, and the
  recovered inventory after `/clear` and after close and reopen is compared entry by entry [2.10].
- Record date, host versions and numbers in `kis/knowledge/`.
Accept: static rerun prints identical numbers; every live number carries host, version and case.

### Phase 1: KIS 0.11.0 (in ../kis-loop-skill, then vendored)
- State stamp: sync writes it; `session-anchor.sh` and the agy anchor print a stale line on branch
  mismatch or code commits after the stamp. Tests: match, branch differs, code commit after stamp,
  `kis/`-only commit after stamp (not stale), no stamp, and a full sync → commit → fresh session.
- Anchors on all four hosts [3]: add Codex SessionStart (hooks.json; installer prints the one-time
  `/hooks` trust step) and cmd SessionStart (`~/.commandcode/settings.json` or project settings);
  define agy reinjection after compaction (its anchor currently suppresses repeats per
  conversation). cmd: an output adapter emitting JSON `additionalContext`, and a reinjection
  strategy after compaction, since its SessionStart has no compact source [2.7]. Live check per
  host in the test home that the model received the anchor: startup, resume, and after compaction
  where the host compacts.
- Recovery contract per decision 4 (SKILL.md, `start`, `check` follow an active-run pointer);
  tests: standalone `kis:start` and `kis:check` during an unfinished run keep pointer-only State.
- Plan review per decision 6, in SKILL.md, `commands/plan.md` and `commands/act.md`. Tests: missing
  review refused, unresolved finding refused, substantive plan edit after review refused, task
  marked done keeps the review valid, reviewed plan passes.
- Pointer-aware State writer per decision 4 in `commands/sync.md`.
- Release 0.11.0; vendor into orch-skill; vendored tree byte-identical to the tag.
Accept: kis-loop-skill gates green; each guard's mutant fails; vendored copy identical.

### Phase 2: front door and close (orch-skill)
- `orch:start` thin router per decision 1; the full ledger, watcher, Herdr and brief references
  load only in Agents mode; the minimal ledger loads in a no-KIS session [2.4]; KIS version check
  and update offer [2.3]. Herdr prerequisite moved out of SKILL.md's unconditional stop.
- `orch:close` per decision 2 (session-close steps slimmed: no retro, no rule numbers).
- Per-host invocation [2]: Claude command wiring, Codex prompts, cmd commands, agy named-step
  instructions (no custom slash commands); installer writes each, `check` verifies each host.
- Retire session-close: installer removes links and the owned package; `check` reports leftovers.
  Upgrade test from the 0.10.0 / 1.0.2 install.
- Remove `/lore:load`, `/lore:retro`, rule numbers; reference grep scoped to `skills/` (migration
  code and fixtures may name session-close).
- SKILL.md under 150 lines; version bump.
Accept: live start and close from an unrelated repo on every host, with and without `kis/`,
outside Herdr; a repo carrying KIS 0.10.1 gets the update offer and works either way; a no-KIS
session closes and a fresh session recovers it with no pane or watcher; Agents escalation inside
Herdr; upgrade test green; measured light start cost.

### Phase 3: run layer (orch-skill)
- Watcher audit: map `orch-watch.py` by function statically, measure feature use from real runs'
  `events.log` and `stats` (legacy run folders hold three), profile only where a proposed cut needs
  evidence the logs lack [2.11]; propose cuts to the owner with savings.
  Keep short-turn completion detection, per-owner delivery and typed-input protection; regression
  tests for anything replaced.
- Ledger/State per decision 4 in `event`, `handoff`, `close`; fresh-session recovery test mid-run.
- Split gate per decision 7 (ledger fields `depends`, `owns`, status `queued`); tests: ordered
  pair, shared file, disjoint pair passes, queue → blocker merge → launch through `orch:task` and
  `event`, and recovery while queued [2.9].
- Cross-CLI diff review before merge in the merge flow; records reviewed commit range.
- Watcher as an orch Herdr plugin, with a readable UI (owner, 2026-10-17; the owner's screenshot of a
  community stage graph is inspiration, not a spec). `herdr-plugin.toml` declares a board pane
  (popup or split, opened by an action bound to a key), actions, and `[[events]]` hooks where they
  can replace polling (measured in the audit). Installed by `bootstrap.sh` (`herdr plugin link`).
  - Board: header (repo, date and time, usage), Next action and Needs-you strip, one box per task
    with state colour, task title, agent CLI/model, pane, age, evidence and context; arrows from the
    split gate's `depends`, side by side without them; Recent with day markers; keys to select and
    open an agent's card. Dates on every time older than today, `none` instead of empty cells, task
    titles kept after a pane closes, owner shown by name.
  - Agents read the same data as plain text (`board --plain`, `show`, `status`); the wake prompt
    carries task title, evidence and the expected next step.
  - events.log: new fields appended only, so old logs still parse; parser, `check`, `stats` and
    existing log tests stay green.
  - Language and library decided in the audit: Python + Textual (pinned; via `uv run --script` or a
    bootstrap venv), stdlib curses, or Node like other Herdr plugins; vet any dependency first.
  - Accept: rendered board checked by eye from real run data (copied legacy runs) at two terminal
    widths and in light and dark; plain output and wake prompt checked by an agent reading them.
Accept: tests green; a live run (one Claude, one Codex agent, scratch repo, test home) shows finish,
wake, mark, review, merge in events.log, and a fresh session recovers the run from State + ledger.

### Phase 4: legacy cleanup
- Per legacy folder: drain or persist the watcher's pending wakes, stop the old watcher and verify
  it is gone [2.1]; list contents and what is kept; move to `<repo>/.orch/` repairing brief,
  handoff and report paths inside the ledger and in every KIS file or kept artifact citing them
  (e.g. tartib `kis/state/current.md`), checking each target resolves [2.2]; restart the watcher
  against the new dir and prove pending events reach their owners; verify `orch:start` recovers
  the run from the new dir.
- Owner approves each deletion (example-app checked by file category first).
- Remove the legacy path from `orch-dir.sh`, `start.md`, `SKILL.md`, watcher; test `.orch/` only.
Accept: recovery verified per repo before deletion; tests green; nothing cited by any State lost.

### Phase 5: install, measure, triage
- `bootstrap.sh update --source .` in the real home; `check` current on all four hosts; Codex
  `/hooks` trust done by the owner.
- Rerun phase 0's probe and cases; report the reduction; gate: no rise in recovery failures,
  forgotten work, approvals or setup interactions.
- Re-triage the old backlog.
Accept: check clean; before/after table in Knowledge; backlog triaged.

## Risks

- cmd has no Herdr kind and agy can be idle with background work: evidence marks stay the proof of
  done, never Herdr state.
- Codex hooks need a one-time trust; until then the Codex anchor does not run.
- Two repos and a vendored copy: phase 1 releases and vendors before phase 2 starts.
- Retiring session-close breaks muscle memory and other repos citing it.
- Live per-host checks cost quota on four CLIs; schedule by usage.
- Deleting 2.4 GB of reports is irreversible; per-folder approval.
