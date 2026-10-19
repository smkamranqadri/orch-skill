# Herdr phase 2 fixtures

Captured from Herdr 0.9.5 in the named `orch-phase2-test` session. `socket-events.jsonl`
contains real `events.subscribe` envelopes for `pane.agent_status_changed` and `pane_closed`.
Repeated status transitions are retained; duplicate close deliveries caused by overlapping
subscriptions are represented once. Claude and Codex records came from one minimal fictional
prompt each using installed Claude Code 2.1.300 (Sonnet 5.5, low) and Codex CLI 0.162.1
(GPT-6.1-Sol, low). The panes were created for this capture and then closed.

`agent-get-claude.json` and `agent-get-codex.json` preserve the real `herdr agent get`
response shape and captured idle records. The fixture paths, host name, and provider session
IDs were replaced with fictional values; other volatile Herdr identifiers remain as captured.

The stream includes startup/unknown, working, done, idle, and close events from the real
provider panes. Herdr did not classify the Codex clarification response as blocked. To supply
that status shape, the stream also includes a blocked-to-unknown lifecycle reported through
Herdr's `pane.report_agent` API on a separate task-created shell pane (`custom:phase2-fixture`,
agent `sample-worker`). Treat those two records as custom-source fixtures, not native Claude or
Codex detection output. The plugin event hook could not be linked for capture because Herdr
0.9.5 stores linked plugin registration globally across sessions; no plugin was linked.
