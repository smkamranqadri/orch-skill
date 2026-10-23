# Plan: spawn and notice fixes

Mode: Standard. Approved by the owner 2026-10-23. Status: done, merged to `main` as `2d6e04a`
2026-10-23; live check passed (see State). Source: bugs seen by the lore-skill orch while
it ran lore 2.0 P1 (2026-10-22); ideas 1 and 15 in `ideas-from-0.12.2.md`. Idea 16 (proof-carrying
handoffs, `orch verify`) is the next cycle, not this one.

## Bugs

1. **Spawn never submits.** `orch spawn` prompts the brief's full text; Claude Code collapses it
   into `[Pasted text #1 +N lines]` and never submits. Seen 3 of 3 Claude spawns; Codex submits.
2. **No finish notice for worktree workers.** Herdr shows the worker stopped
   (`completion_seq == state_change_seq`) while the registry keeps `working` and no notice is sent.
3. **Early notices.** `idle` notices arrive mid-turn; the hook notifies on any change to idle/done
   and ignores `completion_seq`.

## Tasks

1. Diagnose 2 from real event payloads before fixing it (orch, read-only probe).
2. Spawn sends `The user asked for this: <absolute brief path>`, confirms the turn started
   (`working`, or `completion_seq`/`state_change_seq` moved), sends Enter once if not, and fails
   the spawn with a clear error if it never starts. The registry records the spawn's baseline seqs.
3. Hook: `done`/`idle` notices only when the agent's `completion_seq` rose above the stored value;
   `blocked` still notifies at once; `closed` unchanged.
   Changed during the build (owner 2026-10-23): Herdr can end a real turn without
   `completion_seq` and sends false `done` blips, so a terminal status without a rising
   `completion_seq` is rechecked after a 15 s debounce; one notice per turn (`turn_open`).
4. Fix 2 per the diagnosis (cause: pane reuse matched an old closed row; the hook now prefers the
   newest non-closed row).
5. Each fix has a test that fails when its guard is broken (literal mutation, restored and
   byte-identical); full suite passes.

## Acceptance

- Suite: `env -u HERDR_ENV -u XDG_STATE_HOME HOME=$(mktemp -d) ./tests/run.sh` passes.
- Live in Herdr: a Claude worktree worker and a Codex worktree worker each submit on their own,
  produce exactly one `done` notice at the end, and no `idle` notice mid-turn.
- Merging to `main` changes the live plugin (linked to this checkout) used by other orchs, so
  the owner approves the merge moment.

## Agents (owner-approved 2026-10-23)

Builder Codex gpt-6-luna medium in a worktree; reviewer Codex gpt-6.1-sol medium (ran 2 rounds; round 3 verified by the orch with its repros, owner choice);
diagnosis and test runs by the orch with `herdr pane run`.
