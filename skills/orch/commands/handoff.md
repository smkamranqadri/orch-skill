---
description: Hand the orchestrator over to a fresh session at about 150k context: retro, memory sync, status space, ledger and handoff packet, start the successor, then close.
argument-hint: [optional note for the successor]
---

# Orch: handoff (replaces /compact)

Agents keep running. Nothing is closed, removed or committed beyond the memory sync.

1. Retro first (`/lore:retro`, core rule 66) when the lore skill is installed: a compact
   or close loses the detail. Not installed: skip in one line.
2. Session-close steps 1 to 3 and 6 (`~/.agents/skills/session-close/SKILL.md`): KIS sync, KIS
   check, apply (when the repo has `kis/`), the project's status space (when the notes MCP is
   present); each absent one is skipped in one line. Flush applied decisions from the ledger's
   Open decisions into the KIS plan (core rule 57), or leave them in the ledger without KIS.
3. Write the ledger. Refuse to continue while `Next action` is empty or stale.
4. Write `<dir>/handoff-<date>-<n>.md`: line one is the Next action; then paths to the ledger,
   State, briefs and reports (paths, never bodies); decisions since the last handoff; agent-tool
   sub-agents still running, listed as lost; the watcher's pane and pid; skills the successor
   must load. No secrets, no session story.
5. Leave the watcher running; it serves the successor once step 7 points it there.
6. Start the successor in a new pane of this workspace, visible (preference 28), with the same
   kind and model as yourself unless the user says otherwise:
   `herdr pane split --current --direction right --no-focus`, then
   `herdr agent start orch-<n> --kind claude --pane <id> -- --name orch-<n>`, then
   `herdr agent prompt orch-<n> "The user asked for this: take over as orchestrator. Run /orch:start with <dir> up to the board, reply with the Next action, then wait for go. Your handoff is <packet path>." --wait --until idle --timeout 540000`
   (Bash tool timeout 560000).
7. Read the successor's reply (`herdr agent read orch-<n> | tail -10`): it must name the Next
   action from the ledger. Then point the watcher at it
   (`python3 ~/.agents/skills/orch/scripts/orch-watch.py orch <dir> <successor pane id>`), so
   events wake the successor and not you, then `herdr agent prompt orch-<n> "go"`, and tell the user:
   "orch-<n> has the run. Close me."
