# Changelog

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
