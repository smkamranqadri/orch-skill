# Orchestrator workflow, from the school-next transcripts

Source: 11 transcripts in the school-next project folder (29 Sep to 6 Oct 2026). Scripts: extract.py, q1.py,
q2.py, q3.py, q8.py in this folder; events.jsonl is the extracted data. Three sessions are the orchestrator:
92d1e4e9 (29 Sep to 1 Oct), 67154ba8 (1 to 3 Oct), 871230c3 (3 to 6 Oct). Each one was started right after the
previous one was closed (02:16 then 02:17; 14:04 then 14:34). The other eight are short (2 to 80 turns, max
context 36k to 379k): kis start/lessons chats and a few sub-sessions. Shape verified: records have type
user/assistant/system/attachment; usage is on assistant records; one message id repeats per streamed block, so
turns are counted per message id. Task notifications arrive as user records with origin kind "task-notification".
No secrets were quoted. One pasted ssh command with an IP was seen in the user text and is not reproduced.

## 1. Context growth

| session | span | max context | turns | tool calls | top tools |
|---|---|---|---|---|---|
| 92d1e4e9 | 29 Sep 12:20 to 1 Oct 02:16 | 847,783 | 693 | 1,186 | Bash 838, Edit 129, Read 64, Write 55, TaskStop 54 |
| 67154ba8 | 1 Oct 02:17 to 3 Oct 14:04 | 932,174 | 1,993 | 1,981 | Bash 1552, AskUserQuestion 158, Write 57, Read 54, Artifact 33 |
| 871230c3 | 3 Oct 14:34 to 6 Oct 15:41 | 920,992 | 1,495 | 1,513 | Bash 900, AskUserQuestion 134, Agent 133, Write 78, SendMessage 36 |
| be95a768 / adb32f73 | 4 Oct | 379k / 347k | 80 / 48 | 118 / 61 | side sessions with Agent calls |
| a609329f | 3 to 4 Oct | 220k | 31 | 40 | tartib get_item, Bash |
| a2cbae27, 34867ddb, 49f899db, 546696a0, 01841f84 | short | 36k to 88k | 2 to 33 | 1 to 27 | kis start, lessons |

Context is paid again on every turn. Sum of context tokens over all turns: 316M (92d1e4e9), 717M (67154ba8), 658M
(871230c3). Turns above 200k: 599, 1,487, 1,214. Turns above 500k: 305, 490, 646. Median turn context: 470k, 328k,
443k. So the orchestrator lives above 300k almost all the time, and above 500k for a third to half of its turns.

Compactions (system subtype compact_boundary, plus a size drop to about 50k): 92d1e4e9 once (30 Sep 06:29, from
848k); 67154ba8 three times (1 Oct 14:31 from 704k, 2 Oct 06:19 from 493k, 3 Oct 02:51 from 932k); 871230c3 twice
(4 Oct 20:40 from 921k, 6 Oct 00:11 from 798k). The 6 Oct summary opens with the stock phrase "ran out of context", but the user had typed /compact first, so all six were user-triggered. Every compaction left the session at 48k to 65k, then it grew back to 500k+ in a day.

Tool results are 1.3M to 2.2M chars per big session, tool_use inputs 1.0M to 1.4M chars (prompts, Write bodies,
patch scripts), user text only 71k to 177k chars. Bash results are 819k, 1,356k, 805k chars of it.

15 largest tool_result blocks (all sessions; the tool name is matched by id):

| # | session | tool | chars | first 120 chars |
|---|---|---|---|---|
| 1 | 67154ba8 | Artifact | 52,694 | Created a new Artifact at https://claude.ai/artifact/... (version ...) from the Artifact ... |
| 2-5 | 67154ba8 | Artifact (x4) | 52,240 | same "Created a new Artifact" text, four creations in 3 minutes |
| 6 | 67154ba8 | tartib list_items | 49,971 | {"space": "ai-agents", "items": [{"id": 333, "space": "ai-agents", "shape": "note" ... |
| 7 | 92d1e4e9 | tartib get_item | 35,518 | {"id": 269, "space": "ai-agents", "shape": "note", "title": null ... |
| 8 | 871230c3 | Artifact | 34,797 | [Artifact 2242b64e-... (version ...) owned by you, private ... |
| 9 | 92d1e4e9 | tartib get_item | 33,800 | {"id": 267, "space": "ai-agents", "shape": "note" ... |
| 10-11 | 871230c3 | Artifact (x2) | 33,411 | Quickstart. This one result stands in for listing the Artifact types ... |
| 12 | 67154ba8 | Artifact | 33,279 | Quickstart. This one result stands in for listing the Artifact types ... |
| 13 | 92d1e4e9 | tartib get_item | 30,179 | {"id": 269, "space": "ai-agents" ... (same lessons note, read again) |
| 14 | be95a768 | Read | 30,133 | 1 ===== 324 / Agents: core rules / General rules from past sessions ... |
| 15 | 92d1e4e9 | tartib get_item | 28,481 | {"id": 268, "space": "ai-agents" ... |

Note: the biggest single blocks are not agent output. They are the lessons notes (re-read after each compact,
and by each side session) and Artifact tool boilerplate. Bash dominates by volume because there are 3,400
results (3.25M chars, median 308 chars, 64 cat/sed-style reads above 5k, max 21k).

## 2. What the orchestrator reads that it should not

Bash and tool calls in all sessions, classified by command text (n, total chars, median, max, count above 5k):

| category | n | total chars | median | max | >5k |
|---|---|---|---|---|---|
| agent reports and briefs read with cat/sed/head/grep on .md under reports | 357 | 877k | 1,137 | 20.9k | 51 |
| tartib get_item (mostly the lessons notes) | 74 | 678k | 7,107 | 35.5k | 58 |
| kis and docs file reads (cat/sed/head) | 271 | 504k | 797 | 20.8k | 22 |
| Artifact tool (create, quickstart) | 55 | 493k | 1,450 | 52.7k | 10 |
| Read tool | 161 | 465k | n/a | 30.1k | 27 |
| git diff, show, log | 556 | 305k | 183 | 10.1k | 11 |
| logs and background task output files | 426 | 285k | 366 | 11.8k | 4 |
| herdr agent read and pane read (pane reads) | 283 | 273k | 597 | 7.2k | 5 |
| tartib edit_item (echoes the whole note back) | 13 | 113k | 11,568 | 12.9k | 12 |
| tartib list_items | 15 | 101k | 2,285 | 50.0k | 4 |
| herdr agent/workspace/pane list | 79 | 39k | 53 | 6.3k | 1 |

Reading: pane reads are small because the orchestrator already trims them (tail -6, tail -15, head -c 400). The
real bloat is (a) reading agent reports and briefs as whole files, 877k chars over 357 reads, (b) the lessons
notes loaded again and again (get_item 7k median, 678k total; edit_item echoes 11.6k each), (c) KIS and docs files,
(d) Artifact results, (e) git diffs. Count is also a problem: 3,400 Bash results at about 300 chars each is
about 1M chars, and each one adds a turn whose whole context is re-read.

Sample commands:
- `herdr agent read infra --source visible 2>&1 | tail -6` (the trimmed style, typical)
- `herdr agent prompt design "/compact Navigation rollout done (097dfd3); handoff .reports/design-handoff.md; next export code 113; waiting for the user's review." ... ; sed -n '/## Rollout/,$p' .../design-nav.md | head -80`

## 3. How the user talks to the orchestrator

Typed messages (origin kind human; the 280 task-notification and tool-result records are excluded). Real typed
messages after dropping slash-command echoes: 92d1e4e9 71 typed (median 65 chars); 67154ba8 165 (median 52);
871230c3 83 (median 34). Short sessions: 1 to 13 each, median 27 to 323. In 871230c3 the median is 34 chars:
the user mostly approves, redirects, or asks "what else".

Representative quotes:
- Task assignment, loose and parallel: "if any other task can be done then assign and anything need me left me know" (92d1e4e9, 30 Sep).
- Delegating overnight: "we will need slides for tomorrow presentation, one or two agents for marketing content and create two to three versions so i will pick one tomorrow, I am going to sleep, will check tomrrow, so do as you will" (67154ba8, 3 Oct).
- Asking for parallelism: "what else we can in parrallel" (871230c3, 4 Oct) and "anything else we can do" (5 Oct, asked many times).
- Status question: "are three agents working or stopped?" (92d1e4e9, 29 Sep); "one worker is done please check" (871230c3); "what's pending" (871230c3).
- Decisions, terse: "apply" / "approve" / "looks good" / "merge, no concinece utill we give access to anyone so can do whatever we want".
- Decisions with scope: "attendance is all wrong ... let's park attendance for now, we will come back after demo, don't have time to redesing and code" (67154ba8, 2 Oct).
- Review flow: "01a [needs change]: wrong color and wrong deisgn rest is approved" and "ask one by one" (871230c3).
- Model choice per agent: "use ch instead of claude to run the agent only for this task".
- Resource control: "stop guardian as well for now, same pause as d50".
- The user loses the picture: "i feel disconnected now like what is building or what is not, what are pending tasks, like project status, i know kis know but asking agent will take token and reading long files crate friction to do so, what do you suggest" (871230c3, 6 Oct 15:24, the last typed message).

Slash-style routine words from the user: "kis sync and kis check then apply", "resume", "let's compact you too",
"you know the flow". The user also runs shell directly with "!" and bash-input (ssh, check scripts).
AskUserQuestion is used heavily by the orchestrator (158 and 134 calls): the user answers questions one at a time.

## 4. How the orchestrator briefs agents

Counts:
- herdr agent prompt: 394 Bash calls (445 mentions), median command length 750 chars. 90 start with "The user asked for this"; 257 refer to a brief or .md file; 50 send "/compact" to an agent.
- herdr agent start: 38. herdr worktree create: 24 (14 in 92d1e4e9, 10 in 67154ba8). 12 workspace closes, 7 pane closes, 5 worktree removes.
- Agent tool: 146 calls, all in 871230c3 except 15. By type: worker 87, designer 29, explorer 11, researcher 8, general-purpose 8, Explore 1. Median prompt 1,603 chars. None of the worker/designer calls is run_in_background (the harness runs them foreground); 5 general-purpose and 3 research/explorer calls are. 117 worker/designer prompts all start "The user asked for this", and 81 of them name a brief file on disk. SendMessage to a running sub-agent: 37 (all 871230c3).
- Brief files: the orchestrator writes brief-*.md under school-next.reports/ (per agent folder, for example code-fees/brief-fees.md, code-attendance/brief-attendance-ui-resume.md) and gives the agent only a pointer.

Quotes:
1. Agent tool, pointer style: "The user asked for this: build Fees > Concessions and Adjustments (server and screens), queued until the D50 screens merged. Your brief is /Users/mkamran/Repositores/side-projects/school-next.reports/code-fees/brief-fees.md. Read it in full and follow it."
2. Agent tool, resume after limit: "The user asked for this: finish the attendance screens overnight; the previous agent was stopped by the session limit. Your brief is .../brief-attendance-ui-resume.md - read it and follow it exactly."
3. Agent tool, inline scope: "The user asked for this (2026-10-04): three Console changes on the admin-reset branch. Load the lessons first (/lessons:load) with backend and shell gotchas; secrets rules (core 23) are binding: never print a password ... Worktree /Users/mkamran/..."
4. herdr agent prompt: `herdr agent prompt design "You are the design stream. Read .reports/brief-round8-background.md in this worktree and carry it out end to end. The Pen MCP (pencil) is available ... Reply with a short summary when done." --wait --timeout 60000 | head -c 400`
5. herdr agent prompt with decisions: "The user answered your seven band 2 questions; they are A-36 to A-42 in docs/product/academics-requirements.md on main ... Two differ from your recommendations: A-38 import is ALL OR NOTHING ..."
6. Worktree: `herdr worktree create --cwd "$PWD" --branch fb-lists --base main --path ../school-next.wt/fb-lists --label "fb-lists" --no-focus`
7. Start: `herdr agent start code --kind claude --pane w5:p1 -- --model sonnet`

Pattern: named long-lived panes (design, code, app, infra, db-study, mgmt-core, platform, integrate), one worktree
per stream, a "The user asked for this" preamble so the agent knows the instruction is the user's, a brief file for
anything long, "load the lessons first", "reply with a short summary", and agents are told to write their report
and handoff to files (.reports/design-handoff.md). Agents are also compacted by prompt ("/compact Keep: ...").

## 5. How it tracks agents

Counts (all sessions): herdr agent get 194, herdr agent list 203 (156 Bash calls), herdr agent read 240 plus pane
read 56, herdr agent wait 27, send-keys 40. Loops: 152 commands with sleep/until/while; 83 are until/while plus
sleep; 445 commands contain a literal "sleep N" (4,847 seconds of sleep written in commands). Bash with
run_in_background: 346 (161 in 67154ba8, 139 in 92d1e4e9, 46 in 871230c3). TaskStop: 61 (54 in 92d1e4e9). Background
completions come back as user-role task-notification records: 280 (121, 86, 73). Status written in a file:
the orchestrator updates kis/state/current.md with python patch scripts (one 871230c3 command is exactly that).

Pattern in prose: poll the agent's state with `herdr agent get`, which returns agent_status
(working, idle, blocked ...); run the wait as a background Bash so the session is woken by a task-notification;
on wake, read only the last 6 to 25 lines of the pane; then act (prompt, merge, or ask the user). In the third
session a checked-in script, school-next.reports/tools/watch-team.sh, does this: it polls every 20 seconds
and exits as soon as any named agent stops working, printing the status of all agents and the last 15 lines of
the stopped ones. It was started 13 times with the same arguments in 67154ba8. In 92d1e4e9 the same job was
hand-written in each command, then compact was queued behind it.

Quotes:
- `until [ "$(herdr agent get design 2>&1 | grep -o '"agent_status":"[a-z]*"' | cut -d'"' -f4)" != "working" ]; do sleep 15; done; herdr pane read w3:p1 --source recent-unwrapped --lines 25 | grep -v '^\s*$' | tail -10`
- `until herdr agent get mgmt-core ... ["agent_status"]!="working" ...; do sleep 10; done; sleep 2; herdr agent prompt mgmt-core "/compact"` (a watcher that also acts)
- The user, 1 Oct 02:14: "still two backgroun task" (a watcher blocked closing the session).

Consequence: the watchers are children of the orchestrator process. TaskStop was called 54 times in one session
to clear them, and the user was told the session could not close while they ran.

## 6. Handoffs and resets

Counts across the three orchestrator sessions: "/compact" typed or sent 9 times by the user (92d1e4e9 once,
67154ba8 three, 871230c3 two, plus the 50 compact prompts sent by the orchestrator to its own agents);
"resume" typed 4 times (871230c3); one 16,002-char compact summary carrying the stock phrase "ran out of context"; two session
closes with a new session started (30 Sep 19:03 and 1 Oct 01:58 to 3 Oct 13:54). Context numbers the user names:
"it's more than 500k"; "all are on the edge of context".

Timeline and what the user said just before:
- 30 Sep 06:24 (compact, 848k): "your context is also getting full so do kis sync then kis check the update tartib menqal space then compact".
- 30 Sep 19:03 (at 500k+): "let's close the agent pane who is finished and not needed, then kis sycn and kis check then apply then update ai agents tartib space and menqal space and also qa compact, it's more than 500k".
- 1 Oct 01:58 (close, new session): "let's close the agent pane and will close this session too, so kis sycn and kis check then apply then update ai agents tartib space and menqal space and also I will start new session". Then 02:14 "still two backgroun task".
- 1 Oct 14:30 (compact, 704k): "let's compact you too"; then 15:16 "after compact does it have lesson if not please provde and add in your flow too".
- 2 Oct 06:16 (compact, 493k): "kis sync and compact you too then task for code". The orchestrator typed its own `/compact Keep: next = a task for the code agent (w5, idle, compacted; reload lessons first). Agents: design w3 ... Everything else is in kis/state/current.md.` Then 06:27 the user: "you compactd but didn't start, message from you to you before compact => Keep: next = ..." The next action was lost; the user had to paste it back.
- 3 Oct 02:49 (compact, 932k): "let's first compact you"; after compact the session wrote "client demo today. First: server update to engine-v0.5.2 ..." as its own recap.
- 3 Oct 13:54 (close, new session): "lets close the session, what's the workflow to do it, let me know first".
- 4 Oct 20:34 (compact, 921k): "let's prepare for compact, you know the flow", then "/compact", then "resume" at 21:06 and "i am going to sleep now, when session resume after limit renew, contintue with the work, start work that can work in parallel".
- 6 Oct 00:08 (compact, 798k): "i am going to sleep now, keep working, will deploy in the morning, before i go let's compact you". The continuation summary is 16k chars: user requests in order, decisions (decision 20), release steps, agent states.
- 5 Oct 23:01, 6 Oct 04:53, 6 Oct 12:04: "resume" (after usage-limit pauses; agents stopped by "the session limit" are rebriefed from brief-*-resume.md).
- 6 Oct 15:24 (last message): "before I close, one more thing i want to discuss, i feel disconnected now like what is building or what is not, what are pending tasks".

The compact routine is always the same, in this order: kis sync, kis check then apply, update Tartib spaces (ai-agents
and project), tell agents, compact or close. The orchestrator re-loads the lessons notes after every compact (the
get_item results in table 1) because the user asked for it. All 6 compactions were typed by the user (none automatic); they happened at 500k to 930k.

## 7. Time lost

- Repeated identical Bash commands (3+ times, in the big sessions): 36 distinct commands, 171 calls, 135 extra repeats. Top: `zsh .../tools/watch-team.sh 7000 design code` 13 times (67154ba8); `herdr agent wait app --timeout 3600000 | grep -o '"agent_status":...'; herdr agent read app --source visible | tail -30` 9 times; `sleep 20 && .../scratchpad/wat...` 8 times (92d1e4e9).
- Runs of 3 or more consecutive status-check calls with no other action or user message between: 92d1e4e9 7 runs (22 calls, longest 4); 67154ba8 25 runs (111 calls, longest 18); 871230c3 1 run (3 calls). Example (67154ba8, 1 Oct 03:39): agent wait, cat of the task output, agent read, send-keys y, agent read again, for the "app" agent, which was blocked on a permission prompt the orchestrator answered by hand.
- Polling loops: 83 until/while+sleep commands, 445 commands with a literal sleep, 346 background Bash jobs, 280 wake-ups from task notifications. 871230c3 changed style: 3 status runs instead of 25, because it used Agent sub-agents (133 calls) that return their result as one message instead of being polled.
- Turn count as cost: 4,181 assistant turns over three sessions. Bash results have a median of 308 chars (3,400 of them); at a median turn context of 330k to 470k tokens, each small status turn re-reads a context thousands of times larger than the output it fetched.
- The user also loses time: "what's pending", "are three agents working or stopped?", "one worker is done please check", "what else we can do", and the final "i feel disconnected". The user asks the orchestrator what is going on because there is nothing to read at a glance.

## What a replaceable orchestrator must preserve

- A run ledger on disk that already exists in practice in three pieces: agent name, pane/worktree, branch and task per stream (the orchestrator wrote this into its /compact "Keep:" text and into kis/state/current.md); the brief file path per agent (81 of 117 sub-agent briefs and 257 of 394 pane prompts point at a file); and the resume brief (brief-*-resume.md). The ledger must hold the next action, since the 2 Oct compact lost it and the user had to paste it back.
- The same pointer-style brief: "The user asked for this: ... Your brief is <path>. Read it in full and follow it", plus "load the lessons first" and "reply with a short summary". A new orchestrator reads brief paths, not brief bodies.
- Named agents with stable pane ids and worktree paths (design w3, code w5, infra w8, db-study w9; worktrees under school-next.wt), because herdr agent get/read/prompt/wait address them by name.
- Watchers outside the session: watch-team.sh already exists as a script that exits on the first agent that stops, printing the last 15 lines. 346 background jobs were children of the session, 61 TaskStops were needed, and "still two backgroun task" blocked closing. Move the watcher to a detached process that writes status lines to the ledger.
- Compact-like handoff as the user does it today: kis sync, kis check then apply, update the Tartib ai-agents and project spaces, close finished panes, then new session or compact. The new command must do exactly that plus write the ledger and re-open the lessons once, not after every compact.
- Small status reads: the user's status questions ("what's pending", "are agents working or stopped?", "what is building") should be answered from one short ledger file; the 6 Oct message says reading long files and asking agents costs tokens and friction.
- Decisions as short user messages (apply, approve, looks good, "ask one by one", "park X until after demo", "pause guardian same as d50"): the ledger must record each decision, who it applied to, and the parked items, since these are the 34-char median messages the new session cannot re-derive.
- Per-agent resume on limit: agents stopped by the session limit were relaunched from a resume brief overnight; the replaceable orchestrator needs a "resume all stopped" command that reads the ledger, and a rule for what runs in parallel while the user sleeps ("start work that can work in parallel").
- Keep volume down by default: pane reads trimmed to the tail (already the habit: tail -6 to -25); reports and briefs read by head or section, not whole (357 reads, 877k chars); lessons notes read once per session (678k chars of get_item); Artifact tool results (493k) and Tartib edit echoes (113k) kept out of the orchestrator, handed to a sub-agent.
- Orchestrator-only role as stated in the summary: "I brief agents, verify, commit from patches, merge and sync KIS, and never write product code myself". Sub-agent calls (Agent tool, 133 in one session) return one message each and avoid polling; keep that route where an agent need not live in a pane.
