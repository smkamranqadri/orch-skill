# Orchestrator ledger: <project>   (at most 60 lines; `orch-watch.py check <dir>` flags more)
Updated: <UTC time> by <orchestrator name>. Live truth: `scripts/orch-agents.sh`, `git worktree list`.

Next action (<owner pane>): <one line; never empty; agent and path>
Next action (<second owner pane>): <that owner's next step; omit when only one owner>
Each owner exact-matches its Next action line and edits only its own rows. Preserve other owners.
Usage: <paste of `orch-usage.py line` at the last update; ASK marks a CLI at or above 80%>
Waiting on user: <decision, who asked, since when; or none>
Parked: <item, until when, why; or none>

## Pane agents
The status cell starts with one fixed word so `check` can read it: `working`, `done`, `merged`,
`closed`, `gone`, or `open: next cycle <what>`. Any text follows after a comma or colon.
Evidence (verdict marks) lives in events.log, not here.

| name | owner | kind/model | pane | worktree / branch | brief | handoff | status | last event |
|---|---|---|---|---|---|---|---|---|
| code | w5:p2 | claude/sonnet | w5:p1 | ../repo.wt/fees / fees | .orch/code/brief-fees.md | .orch/code/handoff.md | working | 06 14:02 prompted: concessions |

## Sub-agents and background jobs (die with the orchestrator; `--sub` route)
| name | owner | type | started | report | status |
|---|---|---|---|---|---|

## Open decisions (user's words, who they apply to; flush to the KIS plan at close)
- <date time> "<decision>" (applies to: <stream>)

## Done this run (one line each; merged work also has its proof line in State)
- <date> <what, commit>
