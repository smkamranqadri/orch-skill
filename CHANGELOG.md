# Changelog

## 1.0.1 (2026-10-23)

- `orch spawn` sends a one-line pointer to the brief (`The user asked for this: <absolute path>`)
  instead of the brief's text, confirms the turn started, presses Enter once if it did not, and
  marks the agent `not-started` (exit 1, resources kept) if it still never starts. A missing brief
  file is refused.
- Worktree workers get their finish notice again: the hook resolves a reused pane to the newest
  open agent instead of an old closed one.
- No more early `idle`/`done` notices: one notice per turn. A rising `completion_seq` notifies at
  once; a stop without it is rechecked after 15 s (`ORCH_DEBOUNCE_SECONDS`), so Herdr's brief false
  `done` blips are ignored. Sequences reset safely after a Herdr restart. `blocked` still notifies
  immediately.
- `orch close` leaves a pane or workspace open when a newer agent in the same session reuses it.

## 1.0.0 (2026-10-20)

- Board redesigned in the herdrctx style: version header, a ticking `refresh: 1s · last:` line,
  status summary, aligned Name, Status, Project and Title columns, a heading per project with its
  orchs and agents below it, and a `q quit` footer.
- New `orch board` command: runs in place from a plain terminal, opens the full-screen overlay from
  an agent pane.
- `orch close` finishes when Herdr reports the worktree workspace already gone, resumes rows stuck
  in `closing`, and refuses to delete unmerged or newly changed work without `--discard`.

## 0.1.0 (2026-10-19)

Initial public release of orch.

- Closed agent rows remain visible for 10 minutes, then disappear from the board.
- Board sections track each orch, reconcile closed panes, and register from the resolved current pane.

- Herdr plugin for registering coordinators, spawning workers, routing status notices, and
  displaying the live board.
- Shared skill and commands for Claude Code and Codex.
- Installer with local plugin linking, GitHub plugin installation, `check`, and `update`.
- Automatic notice cap, persistent pause and explicit resume, plus registry isolation by Herdr
  session.
