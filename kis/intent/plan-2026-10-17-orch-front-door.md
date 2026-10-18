# Plan: orch as the global front door (path B, after lore 1.0.0)

Status: APPROVED 2026-10-17 by the owner; phases 0-1 done; reviewed again 2026-10-18 (Review section). Phase mode. Current status and proof live in State.

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
   continuing on the old version if declined [2.3]. A KIS below 0.11.0 cannot follow a `Run:`
   pointer, so with the update declined an Agents-mode run keeps its record in the ledger only and
   writes no pointer into that repo's State [3.4].
2. `orch:close` is the single close: closes agents when a run is active, KIS sync + check when
   `kis/` exists, cleans merged worktrees and branches, commits and pushes. session-close retires
   with no alias: the installer removes its links and its installed package
   (`~/.agents/skills/session-close`), keeping modified or foreign content and saying so [5].
3. Substrate stays Herdr. The watcher already reads Herdr's `agent_status` and `completion_seq`
   (`orch-watch.py:454`) [10]; phase 3 audits it by function and real use, then proposes cuts with
   measured savings before any code changes.
4. During a run the ledger is the live record; KIS State holds the pointer line in KIS 0.11's
   shipped format, `Run: orch run active; live record at <path>`, plus one proof line per merge
   [3.2]. Every State writer (KIS sync, orch handoff,
   orch close) recognizes the pointer; decisions flush to Intent at close (handoff passes them on
   in its packet) [4]. KIS's recovery contract (SKILL.md, `start`, `check`) accepts and follows an
   active-run pointer [2.6]. Without KIS, ordinary sessions use a minimal ledger (task, next action,
   decisions, done; no pane, owner or watcher fields) that loads outside Agents mode and that
   `check` accepts without a watcher [2.4].
5. KIS gains a State stamp, as shipped in 0.11.0: `Stamp: <branch> <short sha> <tree>`, written by
   sync from `state-stamp.sh`; `<tree>` fingerprints the working-tree content outside `kis/` and
   `.orch/`, so commits alone never make State stale, a `kis/`-only commit stays quiet, and code
   changed after the sync (committed or not) reports `Stale State` [2.5][3.3]. Every orch State
   writer (handoff, close, merge proof lines) writes the stamp through the same helper. PreCompact
   hook dropped: its output never reaches the model
   on Claude or Codex [1]. Stop gate and Stop sync reminder: not now.
6. Plan review lives in KIS: the rule goes into KIS's SKILL.md (authoritative); `kis:plan` runs a
   cross-CLI review of the written plan (reviewer CLI differs from the author's; harness, model and
   effort proposed for approval; this stricter rule is for plans only, see decision 7 for code) and records what was reviewed (a hash of the plan with its
   designated progress fields, such as Status and task checkboxes, excluded [2.8]) and the
   findings' outcome; `kis:act` refuses to start when the plan has no recorded review or changed after it
   [7]. orch without KIS applies the same rule to a written plan: before implementation it runs the
   review, and the minimal ledger records the reviewer and outcome so recovery keeps it [3.9].
7. orch gains a split gate and a diff review before merge. Reviewer rule for code (owner,
   2026-10-17): a different agent on a different model; the same host is fine (e.g. Sonnet builds,
   Opus reviews) [3.8]. The ledger records per task
   its dependencies and owned paths; `orch:task` compares against every active task, runs ordered
   or overlapping work sequentially, and releases it when the blocker merges [8]. A held task is a
   ledger row with status `queued: after <task>`, which parsing and `check` accept without a watcher
   registration [2.9].
8. Install: `bootstrap.sh` (same pattern as lore). `npx skills add` when public. A host plugin
   (Claude Code or Codex plugin packaging) only if hook wiring proves painful. The orch Herdr plugin
   in phase 3 is separate and in scope [3.13].
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

KIS Stop gate; PreCompact hooks; host plugin packaging and npx publishing (the orch Herdr plugin is
in scope); vendoring the new KIS into repos other
than orch-skill; lore changes; agent-of-empires; trimming KIS start beyond what decision 1 needs.

## Test home and gates (all phases) [12][13]

- Phases 0–4 run against an isolated test home (`HOME=<scratch>/home`, pinned packages: orch
  0.10.0, session-close 1.0.2, KIS 0.10.1 for the baseline; each changed package installed there
  before its live acceptance, hook wiring refreshed, loaded versions and paths printed). The owner's
  real home is updated only in phase 5.
- Gates: orch-skill `tests/run.sh`; kis-loop-skill its validator and every test script its
  AGENTS.md Checks list names (eight at 0.11.0) [3.14], plus `ACTIVE_VERSION`, SKILL metadata and tag agreement for a release. Every new guard
  mutation-checked.

## Phases

### Phase 0: baseline
Status: done 2026-10-17 (`7ef115e` and the agy rerun; numbers in `kis/knowledge/start-cost.md`).
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
Status: done 2026-10-18. KIS 0.11.0 released (`f3b17bb`, tag v0.11.0, pushed) and vendored here.
Builder Claude Sonnet 5.5 (high), reviewer Claude Opus 5.5 (high, read-only), one task at a
time (owner, 2026-10-17; Codex and agy reviewed task 1 before the switch). Order: stamp, plan review, recovery contract and pointer-aware sync,
anchors on four hosts, release and vendor.
- State stamp: sync writes `Stamp: <branch> <short sha> <tree>` from `scripts/state-stamp.sh`;
  `<tree>` fingerprints the working-tree content outside `kis/` and `.orch/`, committed or not.
  The anchor (and so the agy anchor) prints one `Stale State` line on a branch mismatch or a
  changed fingerprint. Owner, 2026-10-17: also catch uncommitted changes the last sync did not
  see (the one stale recovery in the baseline); content, not commits, so sync-then-commit stays
  quiet. Tests: match, branch differs, code commit after stamp, `kis/`-only commit (quiet), code
  and State committed together after sync (quiet), uncommitted or untracked code (stale), dirt
  that existed at sync (quiet), no stamp (quiet), linked worktree with the real index untouched,
  and a full sync → commit → fresh session.
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
- First, before any orch change: the interactive baseline [3.12]. In the test home with orch 0.10.0
  and KIS 0.11.0, run fixed interactive cases per host (cmd turns 1 and 2, agy across turns, Codex
  with the project hook trusted and untrusted, Claude start and close) and count approvals and
  setup steps per case; record them in `kis/knowledge/start-cost.md` next to the headless baseline.
- `orch:start` thin router per decision 1; the full ledger, watcher, Herdr and brief references
  load only in Agents mode; the minimal ledger loads in a no-KIS session [2.4]; KIS version check
  and update offer [2.3]. Herdr prerequisite moved out of SKILL.md's unconditional stop.
- `orch:close` per decision 2 (session-close steps slimmed: no retro, no rule numbers).
- Per-host invocation [2]: Claude command wiring, Codex prompts, cmd commands, agy named-step
  instructions (no custom slash commands); installer writes each, `check` verifies each host.
- Retire session-close: installer removes links and the owned package; `check` reports leftovers.
  Upgrade test from the 0.10.0 / 1.0.2 install. In the same phase, rewire `commands/handoff.md`
  (today it loads session-close steps 1-3 and 6) and SKILL.md's `/session-close` pointer to
  `orch:close`; a handoff check runs right after the retirement upgrade [3.5].
- Remove `/lore:load`, `/lore:retro`, rule numbers; reference grep scoped to `skills/` (migration
  code and fixtures may name session-close).
- SKILL.md under 150 lines; version bump.
Accept: live start and close from an unrelated repo on every host, with and without `kis/`,
outside Herdr; a repo carrying KIS 0.10.1 gets the update offer and works either way, and with
the update declined an Agents run recovers from the ledger with State untouched [3.4]; a no-KIS
session with a written plan is refused until its review is recorded [3.9]; handoff works after
session-close is gone [3.5]; a no-KIS
session closes and a fresh session recovers it with no pane or watcher; Agents escalation inside
Herdr; upgrade test green; measured light start cost.

### Phase 3: run layer (orch-skill)
- Watcher audit: map `orch-watch.py` by function statically, measure feature use from real runs'
  `events.log` and `stats` (legacy run folders hold three), profile only where a proposed cut needs
  evidence the logs lack [2.11]; propose cuts to the owner with savings.
  Keep short-turn completion detection, per-owner delivery and typed-input protection; regression
  tests for anything replaced.
- Ledger/State per decision 4 in `event`, `handoff`, `close`; fresh-session recovery test mid-run,
  including a standalone `kis:start` reading the `Run:` pointer orch wrote [3.2]; stamp tests: a merge
  with its proof line written stays quiet, later code dirt reports stale, ledger-only changes stay
  quiet [3.3].
- Split gate per decision 7 (ledger fields `depends`, `owns`, status `queued`); tests: ordered
  pair, shared file, disjoint pair passes, queue → blocker merge → launch through `orch:task` and
  `event`, and recovery while queued [2.9].
- Diff review before merge in the merge flow (reviewer rule: decision 7); records the reviewed
  commit range; merge refuses when the review is missing, failed, or older than the branch head (a
  commit after the review); each refusal tested and mutation-checked [3.10].
- Model matrix (owner, 2026-10-17): orch ships a provider x model x effort matrix (what each can do,
  what it costs, measured use) and picks harness, model and effort from it when it proposes an agent.
  Seed: `kis/knowledge/models.md`. A command rebuilds it on demand for whoever installs orch: it finds
  the installed CLIs and their model lists (`codex` models cache, `cmd --list-models`, `agy models`,
  Claude's model ids), asks the user which plans they have, fetches current prices with sources, and
  keeps the user's own measured notes. The user's matrix and notes live outside the package
  (`~/.agents/orch/models.md`), so an orch update never replaces them; a rebuild merges new models
  and prices in and keeps the notes [3.7]. Accept: rebuilt from scratch in the test home it lists
  exactly the installed CLIs' models with their supported efforts and each price's source; two
  rebuilds and an orch update keep the notes; an unavailable CLI or price page is reported, not
  guessed; picks follow decision 7's reviewer rule for code and decision 6's for plans [3.7][3.8].
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
  - Lifecycle: the watcher process is owned by the run, not by the board pane. Opening the board
    never starts a second watcher, and closing it never stops delivery [3.6].
  - Accept: rendered board checked by eye from real run data (copied legacy runs) at two terminal
    widths and in light and dark; plain output and wake prompt checked by an agent reading them;
    `herdr plugin link` install, the key action, closing the board, opening it twice, a watcher
    restart, and pending wakes after an owner transfer each tested [3.6].
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
- Update the probes first, keeping the workload of the phase 0 cases comparable [3.11]:
  `measure-start.sh` counts `orch:start` and `orch:close` instead of the retired session-close;
  `measure-live.py` enters through the front door, closes with `orch:close`, seeds a Stamp and a
  valid plan-review record in its fixtures, and adds a stamped-recovery case.
- Rerun the probes; report the reduction; gate: no rise in recovery failures, forgotten work or
  questions to the owner (the measure phase 0 used). Approvals and setup steps were not measurable
  headless, so the same interactive cases as phase 2's interactive baseline are rerun, and the gate
  is no rise per host and case against that baseline; a one-time trust step counts once per
  project, not per session [3.12].
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

## Review
- Reviewed: 2026-10-18 by codex gpt-6.1-sol (high); plan hash 2c86ee76814e
- [fixed] 3.1 no Review record in the 0.11 format - this section, hash taken last
- [fixed] 3.2 pointer format differed from KIS's shipped Run line - decision 4 uses the shipped format; phase 3 tests standalone kis:start on it
- [fixed] 3.3 decision 5 described the old commit-based stamp - decision 5 is the shipped content fingerprint; orch writers use the helper; phase 3 stamp tests
- [fixed] 3.4 KIS below 0.11 cannot follow the pointer - decision 1 fallback (ledger only, State untouched) and a phase 2 acceptance test
- [fixed] 3.5 handoff loads session-close, retired in phase 2 - phase 2 rewires handoff and checks it right after the retirement
- [fixed] 3.6 watcher plugin lifecycle undefined - the run owns the watcher; phase 3 tests install, key, close, reopen, restart, transfer
- [fixed] 3.7 model matrix rebuild under-specified - notes in ~/.agents/orch/models.md; efforts, price sources, preserved notes, discovery failure tested
- [fixed] 3.8 cross-CLI diff review vs "different agent and model" - decision 6 keeps cross-CLI for plans; decision 7 adopts the owner's code rule
- [fixed] 3.9 no-KIS plan review missing - decision 6 runs it before implementation and records it in the minimal ledger; phase 2 test
- [fixed] 3.10 merge did not refuse missing, failed or outdated reviews - phase 3 refusal checks, mutation-checked
- [fixed] 3.11 phase 5 probes still on kis:start, sync and session-close - phase 5 updates both probes first, workloads kept comparable
- [fixed] 3.12 approval and setup gate had no baseline - phase 2 starts with an interactive baseline; phase 5 reruns the same cases (second pass found the first fix incomplete)
- [fixed] 3.13 out of scope excluded plugins - host plugin packaging excluded, the orch Herdr plugin in scope
- [fixed] 3.14 stale KIS gate count - gates name every script in KIS's AGENTS.md Checks list
