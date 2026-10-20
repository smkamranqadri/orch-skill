# Changelog

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
