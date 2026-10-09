---
description: Hand the orchestrator over to a fresh session at about 150k context: retro, memory sync, status space, ledger and handoff packet, start the successor, then close.
argument-hint: [optional note for the successor]
---

# Orch: handoff (replaces /compact)

Owner is your orchestrator pane id. One run and watcher serve all owners. Edit only rows
owned by you and exact-match `Next action (<owner>):` when updating it; preserve every other
owner's line. Legacy rows without an owner fall back to `<dir>/orchestrator`; claim them only
when that default is you: pin them with `move <dir> <agent>... --from <your pane id>
--orch <your pane id>` and record the owner in their ledger rows.

Agents keep running. Nothing is closed, removed or committed beyond the memory sync.

1. Retro first (`/lore:retro`, core rule 66) when the lore skill is installed: a compact
   or close loses the detail. Not installed: skip in one line.
2. Session-close steps 1 to 3 and 6 (`~/.agents/skills/session-close/SKILL.md`): KIS sync, KIS
   check, apply (when the repo has `kis/`), the project's status space (when the notes MCP is
   present); each absent one is skipped in one line. Flush applied decisions from the ledger's
   Open decisions into the KIS plan (core rule 57), or leave them in the ledger without KIS.
3. Update only your ledger rows and `Next action (<owner>):`. Refuse to continue while your
   line is empty or stale; preserve other owners' lines.
4. Write `<dir>/handoff-<date>-<n>.md`: line one is the Next action; then paths to the ledger,
   State, briefs and reports (paths, never bodies); decisions since the last handoff; your agent-tool
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
   action from the ledger. Then transfer only your agents
   (`python3 ~/.agents/skills/orch/scripts/orch-watch.py move <dir> <your agent>...
   --from <your pane id> --orch <successor pane id>`). A refusal leaves every registration
   unchanged; resolve the owner mismatch before proceeding. Pending events follow those agents.
   Exact-match and transfer your ledger rows and Next action line to the successor; other owners
   keep theirs. With no owned agents, transfer only your Next action line. Never change the
   legacy default as a handoff shortcut. Then `herdr agent prompt orch-<n> "go"`, and tell the user:
   "orch-<n> has the run. Close me."
