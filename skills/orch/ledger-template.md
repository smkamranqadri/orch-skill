# Orchestrator ledger: <project>
Updated: <UTC time> by <orchestrator name>. Live truth: `herdr agent list`, `git worktree list`.

Next action: <one line; never empty; what the orchestrator does next, with the agent and path>
Waiting on user: <decision, who asked, since when; or none>
Parked: <item, until when, why; or none>

## Pane agents
| name | kind/model | pane | worktree / branch | brief | handoff | status | last event |
|---|---|---|---|---|---|---|---|
| code | claude/sonnet | w5:p1 | ../repo.wt/fees / fees | .orch/code/brief-fees.md | .orch/code/handoff.md | working | 06 14:02 prompted: concessions |

## Sub-agents and background jobs (die with the orchestrator)
| name | what | started | report | status |
|---|---|---|---|---|

## Watcher
pane <id>, pid <n>, wakes: <orchestrator pane>, agents: <names> (<dir>/agents.txt), log: <dir>/events.log

## Open decisions (user's words, who they apply to; flush to the KIS plan at handoff)
- <date time> "<decision>" (applies to: <stream>)

## Done this run (one line each; move to KIS at handoff when the repo has kis/)
- <date> <what, commit>
