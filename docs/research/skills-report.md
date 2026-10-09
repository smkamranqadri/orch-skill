# Existing skills and tools for a replaceable multi-agent orchestrator

Date: 2026-10-06. Read-only research; nothing installed or run. Page text came through a summarising fetcher, so details marked (unverified) were not seen in raw source.

## Method
- Registry: `npx skills find` (as find-skills describes), queries: orchestrator, multi-agent, agent handoff, session handoff, context management, worktree agents, agent ledger, swarm. Raw output: scratchpad/orch/search.log.
- Result: the registry is noisy. Ranking follows install counts, so unrelated skills lead (azure, feishu, marketing). No skill there provides a run ledger. Only the handoff skills were relevant.
- Then web: Anthropic Claude Code docs, Codex docs, GitHub/docs.rs repos.

## Finds (8)

### 1. Claude Code background sessions / agent view (Anthropic, first-party)
https://code.claude.com/docs/en/agent-view.md
- A supervisor process runs each `claude --bg` session as its own process; sessions survive closing the terminal.
- Ledger already exists: `~/.claude/daemon/roster.json` (running sessions), `~/.claude/jobs/<id>/state.json`, `CLAUDE_JOB_DIR` per session, `~/.claude/daemon.log`. Isolated worktrees at `.claude/worktrees/<session-id>/`.
- Borrow: `claude agents --json [--all]` as the machine-readable roster for resume; `claude logs|attach|stop|respawn|rm <id>`; resume by name (`claude --resume "<name>"`); recovery rules (failed within 48h, stopped after).
- Borrow for watchers: the supervisor model (process outside the session restarts workers). Our ledger should store session ids/names and read the roster, not duplicate it.
- Avoid: copying the roster. Claude-only; does not cover Codex panes or briefs. Idle sessions stop after ~1h (conversation kept on disk). Page was partly read (first 100k of 133k chars).

### 2. Claude Code agent teams (Anthropic, experimental)
https://code.claude.com/docs/en/agent-teams
- Lead plus teammates; shared task list (pending / in progress / completed, dependencies, file-lock claiming) at `~/.claude/tasks/{team}/`; team config at `~/.claude/teams/{team}/config.json` (holds session ids and tmux pane ids); mailboxes as JSON at `~/.claude/teams/{team}/inboxes/{agent}.json`.
- Borrow: task states plus dependency model for the ledger; `TeammateIdle` / `TaskCreated` / `TaskCompleted` hooks (exit 2 sends feedback) as quality gates; the rule "task list persists, config removed at session end".
- Avoid as the base: the docs list "No session resumption with in-process teammates" (`/resume` does not restore them), one team per session, lead fixed for its lifetime, status can lag. That is exactly the replaceable-orchestrator gap, so a disk ledger must live outside the session.

### 3. Claude Code cross-session messaging and Channels (Anthropic)
https://code.claude.com/docs/en/cross-session-messaging.md and https://code.claude.com/docs/en/channels.md
- Per-session Unix socket (`CLAUDE_CODE_MESSAGING_SOCKET`, token `CLAUDE_CODE_MESSAGING_TOKEN`) lets a script or hook post into a session; `SendMessage` with `notify_when_idle` gives one notice when another session next goes idle or exits (12h expiry; v2.1.236+).
- Channels (research preview): an MCP server pushes external events (webhooks, CI) into a running session; needs `--channels`, claude.ai auth.
- Borrow for external watchers: a watcher can post a status line to the orchestrator socket instead of the orchestrator polling. `notify_when_idle` replaces polling for "agent done".
- Avoid: depends on version, auth and preview flags; held-message rules (bypass vs prompting sessions) can drop messages. Treat as an optional fast path; the ledger file stays the source of truth.

### 4. Codex subagents (OpenAI docs)
https://developers.openai.com/codex/subagents.md (redirects to https://learn.chatgpt.com/docs/agent-configuration/subagents.md)
- Config keys in `config.toml` `[agents]`: `enabled`, `max_concurrent_threads_per_session`, `default_subagent_model`, `default_subagent_reasoning_effort`, `interrupt_message`. Inspect via `/agent`; steer, stop, close child threads by asking.
- Borrow: a concurrency cap and default model/effort fields in the ledger header.
- Avoid: no documented persistence or resume of child threads on that page (not stated; unverified beyond it), so no ledger help. Codex only spawns subagents when asked (per search summary, https://developers.openai.com/codex/subagents).

### 5. Tutti (Rust crate, multi-agent CLI)
https://docs.rs/tutti (v0.9.0 per search; repo URL and star count unverified)
- Spawns Claude Code/Codex/Aider in tmux, one git worktree per agent, `tutti.toml` workflows.
- Has all four parts: checkpoints `.tutti/state/workflow-checkpoints/<run_id>.json` with `tt run --resume <run_id>`; handoff packets `tt handoff generate <agent>` (markdown in `.tutti/handoffs/`) and `tt handoff apply`; `tt watch` and `tt serve` (SSE dashboard); `tt diff|land <agent>`.
- Borrow: the shape of the ledger (run id, per-agent entries), handoff packet as a markdown file, `land` step that merges a worktree and cleans up.
- Avoid: a whole runtime (tmux server, dashboard); we want a skill plus files. Maturity unverified.

### 6. Bernstein (deterministic orchestrator)
https://github.com/sipyourdrink-ltd/bernstein (the fetch of github.com/chernistry/bernstein reported this as the correct repo; owner mapping unverified). 1.4k stars, beta, solo-maintained per the same fetch.
- State in `.sdd/` (journal, lineage spine, `.sdd/runs/<run_id>/` checkpoints); `bernstein workflow resume <run_id>` resumes at the first incomplete node and rejects a changed manifest digest; per-task git worktrees.
- Borrow: resume = "first incomplete node", plus a digest of the plan so a resume refuses a changed brief. Append-only journal as the ledger shape.
- Avoid: Ed25519 receipts, HMAC audit chains, replay verification are over-scoped for us. No LLM in the loop is the opposite of our orchestrator.

### 7. Gas Town (gt)
https://github.com/gastownhall/gastown (fetched summary: 18.3k stars, Go 1.26.2+, git 2.20+, tmux 3.0+)
- "Hooks" are git-worktree persistent storage that survive crashes; "beads" are git-backed work items; "convoys" bundle beads; `handoff` refreshes an agent's context; `seance`/resume finds earlier sessions via `.events.jsonl`; Witness (per-rig) and Deacon (cross-rig) are watchdog layers that detect stuck agents.
- Borrow: the idea that work state lives in git/files, not in a session; a handoff that reloads decisions without re-reading code; a three-tier watcher split (per-agent, supervisor).
- Avoid: heavy vocabulary and a big system (373 open issues); do not adopt its terms. Detail of event file format unverified.

### 8. mattpocock/skills: handoff and claude-handoff
https://skills.sh/mattpocock/skills/handoff (923.5K installs) and https://skills.sh/mattpocock/skills/claude-handoff (347.7K installs); install counts from `npx skills find`.
- `handoff`: writes a compacted summary for a fresh agent, references existing artifacts by path/URL instead of copying, redacts secrets, has a "suggested skills" section, saves to the OS temp directory.
- `claude-handoff`: writes the summary then launches `claude --bg --name "<name>" "<summary>"` (named, tracked via `claude agents`).
- Borrow: the handoff-content rules (link artifacts, redact secrets, name the next skills) and the `--bg --name` launch for the successor.
- Avoid: temp-dir storage (lost on reboot, not found by a later resume); it has no ledger and no watchers. Single-agent handoff only.
- Also seen: PaulRBerg/agent-skills claude-handoff and codex-handoff (https://claudeskills.info/skills/paulrberg/agent-skills/codex-handoff/): plan in Claude, hand approved work to 1-5 Codex CLI agents. Only a search-result summary was read (unverified).

Also noted, not studied: Crew https://github.com/pikehouse/crew (`.crew/state.json` agent registry, `.crew/logs/<agent>/`, 0 stars, per fetch); Sage https://raw.githubusercontent.com/youwangd/SageCLI/main/README.md (one bash script, file-based inbox/workspace/results dirs, needs bash 4, jq, tmux; ledger commands not verified).

## Which already provide a run ledger or resume-from-file flow?
- Ledger plus resume from file: Tutti (checkpoint json, `--resume <run_id>`), Bernstein (`.sdd/runs/<run_id>/`, `workflow resume`), Crew (`.crew/state.json`, `claude --print --resume <session>`), Gas Town (git-backed hooks, seance).
- First-party roster plus resume: Claude Code `~/.claude/daemon/roster.json`, `~/.claude/jobs/<id>/state.json`, `claude agents --json`, `claude --resume <name>` (agent-view page above).
- Handoff file only: mattpocock handoff skills.
- None found as a plain installable SKILL.md that combines ledger, resume, handoff and external watchers. The skills.sh results do not include one, so a skill is still worth writing, thin, over Claude's own roster.

## Recommended borrowings for our four parts
1. Ledger: one file per run (id, plan digest, per-agent rows: name, tool, session id, pane, worktree, brief path, handoff path, status, watcher pid/log). Task states and dependencies from agent teams; journal shape from Bernstein; per-agent rows from Tutti. Store Claude session ids and read `claude agents --json` for live truth.
2. Resume: "orient from ledger, then reconcile with the roster and `git worktree list`; continue at the first incomplete item" (Bernstein, Tutti). Refuse if the plan digest changed.
3. Handoff: markdown packet that links artifacts, redacts secrets, names next skills (mattpocock); launch the successor with `claude --bg --name` (claude-handoff); write the ledger first, store the packet in the repo or scratchpad, not the OS temp dir.
4. Watchers: run outside the session (supervisor idea from agent view and Gas Town's Witness/Deacon); report with `notify_when_idle` or the session socket where available, otherwise a log file plus pid in the ledger.

## Cautions
- Agent-team and channel features are experimental or research preview (https://code.claude.com/docs/en/agent-teams, https://code.claude.com/docs/en/channels.md).
- Team config holds pane ids and says not to edit it by hand, so do not write into it.
