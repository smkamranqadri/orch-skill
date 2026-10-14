# Plan: six review findings against current state

Status: COMPLETE — six findings resolved and verified; transcript investigation delivered.

Scope approved by the user and the Part A resume brief, 2026-10-14. Standard mode;
continue plan, act and sync without routine questions. Current status and proof live in State.

- Item 1: replace obsolete live-install facts in lore Knowledge with lore 0.5.0,
  current discovery links, commands and backend config; preserve accurate newer history.
- Item 2: read Tartib 333; accept existing lore wording when already satisfied.
- Item 3: inspect current orch State; preserve replacement proofs when old claims are gone.
  If old claims remain, qualify missing evidence rather than manufacture historical proof.
- Item 4: match the yolo brief's version heading to current orch, that line only.
- Item 5: make session-close refer to the lore store and conditional notes-backend status
  space; bump only if needed, never downgrade.
- Item 6: provide the exact verified ledger correction in the report, leaving the shared
  ledger's rows and Next actions to its orchestrator.

Acceptance: no old skill/command names in lore Knowledge; live note read-back;
current State inspection; byte diff proving only the yolo heading changed;
full suites in both worktrees with full logs read; report, handoff and one patch per item.
No runtime guards change, so no new guard tests or mutations are needed.

Out of scope: Part B, full-permission implementation, unrelated cleanup, shared ledger writes,
global installs, commits and pushes. Installation/check follows review and integration.
Risk: concurrent shared-store writers; lore load uses the snapshot read-only, no queue replay,
refresh or retrospective writes. Historical proof is attributed, never upgraded to fresh proof.
KIS: this plan holds scope; Knowledge changes for item 1; State records branch and fresh checks.

Close authorization (2026-10-14): user requested commit/push/close and approved KIS cleanup.
This supersedes the earlier no-commit/no-push restriction for the completed review changes.
