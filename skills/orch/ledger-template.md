# Orchestrator ledger: <project>
Updated: <UTC time> by <orchestrator name>. Live truth: `herdr agent list`, `git worktree list`.

Next action (<owner pane>): <one line; never empty; agent and path>
Next action (<second owner pane>): <that owner's next step; omit when only one owner>
Each owner exact-matches its Next action line and edits only its own rows. Preserve other owners.
Usage: <paste of `orch-usage.py line` at the last update; ASK marks a CLI at or above 80%>
Waiting on user: <decision, who asked, since when; or none>
Parked: <item, until when, why; or none>

## Pane agents
| name | owner | kind/model | pane | worktree / branch | brief | handoff | status | last event |
|---|---|---|---|---|---|---|---|---|
| code | w5:p2 | claude/sonnet | w5:p1 | ../repo.wt/fees / fees | .orch/code/brief-fees.md | .orch/code/handoff.md | working | 06 14:02 prompted: concessions |

## Sub-agents and background jobs (die with the orchestrator; `--sub` route)
| name | owner | type | started | report | status |
|---|---|---|---|---|---|

## Watcher
pane <id>, pid <n>, wakes: <owners per agents.txt>, agents: <names> (<dir>/agents.txt), log: <dir>/events.log

## Open decisions (user's words, who they apply to; flush to the KIS plan at handoff)
- <date time> "<decision>" (applies to: <stream>)

## Done this run (one line each; move to KIS at handoff when the repo has kis/)
- <date> <what, commit>
