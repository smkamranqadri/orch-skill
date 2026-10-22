# Ideas kept from orch 0.12.2

The old build was removed from the tree on 2026-10-19 and stays in git history at `613aa67`
(paths below are under `archive/` at that commit; read with `git show 613aa67:archive/<path>`).
Scouted 2026-10-19 by a Codex agent; items 1, 3 and 12 were checked against `main` by the
orchestrator. None is approved work: each needs an owner decision and a plan before building.
Effort S/M/L includes tests.

## Hardening candidates (verified gaps in v1)

1. **Completion sequence.** `hook.py` ignores `completion_seq`, so a short turn between two events
   can be missed. Old: `skills/orch/scripts/orch-watch.py` `Watcher.poll`; tests in
   `tests/orch-watch-tests.py` (`test_short_turn_is_caught_by_completion_seq`). M, plugin/tests.
2. **Timeout on Herdr calls.** `orchlib.herdr` has no timeout and runs under the registry lock; one
   hung call blocks every hook and CLI command. Keep the outage-versus-missing-agent distinction.
   Old: `orch-watch.py` `herdr`, `agent_list`; `test_herdr_down_does_not_busy_poll`. S, plugin.
3. **Board text safety.** Combining marks count as cells and control characters in names are not
   stripped. Old: `skills/orch/plugin/board` `clean`, `cells`; PTY harness
   `tests/orch-plugin-terminal.py`. M, board/tests.
4. **Typing race.** Notices can land on an owner who is typing. Old: `typed_text`,
   `wake_owner`, three tests in `orch-watch-tests.py`. Parser is Herdr/agent-version specific and
   never atomic. M, plugin.
5. **Literal-mutation runner.** Reusable runner that demands the named test fails and verifies
   restore with `cmp`: `tests/mutate-orch-plugin.py` (120 lines). S, tests.
15. **Spawn never submits.** (Found in v1 on 2026-10-22, not from 0.12.2; numbered last so the
    others keep their numbers.) `orch spawn --brief FILE` pastes the whole brief into a Claude
    worker's input box ("[Pasted text #1 +65 lines]") and never sends Enter, so the worker sits
    idle while the spawn looks done; seen 3 of 3 times (lore-plan-review, lore-p1-reads,
    lore-p1-store), worked around with `herdr pane send-keys <pane> Enter`. It also breaks the
    skill's own rule to send only `The user asked for this: <brief path>`. Fix: send the pointer
    line, wait for `agent_status` working or `completion_seq` to move, send Enter once if still
    idle, and report a spawn that never starts. Tartib #524. S, plugin/tests.
16. **Proof-carrying handoffs and `orch verify`.** (From lore 2.0 P1, 2026-10-22.) Worker reports
    were wrong in ways only checking caught: a cited final test log that did not exist, a guard
    that survived its mutation left out of the handoff, swapped counts, a reviewer's wrong sum.
    The orch re-verified by hand each time. Proposal, prototyped in lore-skill
    `.orch/lore-2.0/{p1-common.md,review-common.md,verify.sh}`:
    - `references/proof.md`, appended to every brief by `orch spawn`: builders record `run_log`
      (last line `exit=0`), `run_sha256`, `tree_sha256` (`git diff HEAD --binary` plus untracked
      files' sha256, taken right after the final run) and a `mutations.log`, one line per guard
      with `tripped=` and `restored byte-identical=`. Reviewers ship a repro script that takes a
      checkout and prints `F<n> REPRODUCED|NOT-REPRODUCED|MANUAL`; the same script proves the fix
      round (`NOT-REPRODUCED`).
    - `orch verify NAME`: knows the worker's role and worktree from the registry. Build: log
      exists, hash matches, `exit=0`, tree unchanged since the run, latest line per guard tripped
      and restored. Review: run the repro script against the reviewed tree, then after fixes. Then a
      clean detached-worktree `tests` run in a plain pane (`herdr pane run`), never an agent.
      Output is PASS/FAIL lines only, so the orch reads a verdict, not prose.
    - Notices: send "done" only when the handoff's proof block exists (also fixes idea 15's early
      notices). `orch board` shows proof state: missing, failing, passing.
    The prototype caught its own first bug on real data (a worker's log had extra columns). M,
    skill/plugin/tests.

## Feature candidates (new product decisions)

6. **Review bound to a branch range.** Record base/head SHAs and a verdict; merge-check rejects a
   changed tip. Old: `scripts/orch-gate.py` `cmd_review`, `cmd_merge_check`. M, skill/plugin.
7. **Evidence and attention on the board.** Reported vs verified vs merged marks; unacknowledged
   finish age. Old: `references/visibility.md`, `orch-watch.py` `needs_you`. M, board.
8. **Handoff packet with acknowledgment.** Successor states the next action before transfer. Old:
   `commands/handoff.md`. M, skill.
9. **Observed-model check and reviewer independence.** Read the running model back; reject
   self-review via aliases. Old: `scripts/orch-model.sh`, `orch-models.py` (exact matching only).
   M, plugin/skill.
10. **Task title and artifact paths in the registry, plus a compact diagnostic card.** Old:
    `orch-watch.py` `show_card`. M, plugin/board.
11. **Task queue with dependencies and file-overlap admission.** Old: `orch-gate.py` `decide`,
    `cmd_admit`. L, plugin/skill.
12. **Quota advisory with honest freshness.** Old: `scripts/orch-usage.py`; exclude the unofficial
    billing endpoint and statusline changes. M.
13. **Design-review packet reference.** Old: `references/design.md`, `scripts/design-pages.py`.
    M, skill/docs.
14. **Recovery-completeness and latency measurement.** Old: `kis/intent/plan-2026-10-17-orch-front-door.md`
    (decision 10), `orch-watch.py` `agent_stats`. M.

## Fixtures

Dirty-run cases (stale ownership, missing briefs, malformed event lines) in
`tests/fixtures/visibility/` and `tests/fixtures/board/`; recreate with fictional data when the
related field lands.

## Rejected

Watcher process and signal files, Markdown ledger, global front door and no-KIS mode, four-host
support, automatic matrix rebuild, automatic successor launch and quota-driven host switching,
legacy install paths, real-run prose and private paths.
