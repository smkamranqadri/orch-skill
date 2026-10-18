# Phase 3 watcher decisions (owner, 2026-10-18)

From the watcher audit (`orch-skill.wt/reviews/watcher-audit.md`, Sonnet 5.5, read-only, 2026-10-18).
These apply phase 3 of `plan-2026-10-17-orch-front-door.md`; that plan's text is unchanged.

- Cuts: all of C1-C8 now.
  - C1 drop `--next`; C2 drop `orch-watch.sh`; C3 one typed-input reader; C8 `stats`/`show` docs out of
    what Agents mode loads (one pointer line stays; `stats` stays shipped).
  - C4 drop the ledger `## Watcher` section; the pid lives in `watcher.pid`; old ledgers read tolerantly.
  - C5 usage refresh leaves the watcher loop (the board reads the cache).
  - C6 Herdr `[[events]]` (`pane.agent_status_changed`, `pane.closed`) wake the watcher; the poll becomes a
    60 s safety net that still reads `completion_seq`, so short turns are still caught (latest 60 s late).
    A live short-turn test with a Haiku agent runs as acceptance, not as a gate.
  - C7 headless `watch` once the board plugin exists (same phase).
- Must keep: short-turn completion detection, per-owner delivery, typed-input protection.
- Legacy logs (350 of 1018 lines fail today's parser): archived in phase 4; the parser stays strict.
- Board plugin: Python stdlib curses first (shares the watcher's parsing); Textual (pinned, hashed, via
  uv) only if the box-and-arrow board proves too costly in curses.
