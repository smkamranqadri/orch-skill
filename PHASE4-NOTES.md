# Phase 4 board preview

Text preview rendered 2026-10-19 from the fictional registry fixture. The live Herdr pane was not opened, per the brief; the owner can review the live pane after linking the plugin. The 60-column footer shortens the path from the left and keeps the registry filename visible.

Commands:

```sh
python3 plugin/board.py --once --width 100 --registry tests/fixtures/board-registry.json
python3 plugin/board.py --once --width 60 --registry tests/fixtures/board-registry.json
```

## 100 columns

```text
ORCH BOARD · 2 projects · 3 orchs · 5 agents
Legend: ! blocked; * orphan; working; idle; done; unknown
----------------------------------------------------------------------------------------------------
STATE              | HIERARCHY PATH                                     | HOST / MODEL
copperfield · 2 queued notices
BLOCKED !          | copperfield / blocked-spruce-worker | codex GPT-6-Luna
BLOCKED !          | copperfield-review | unknown · Q:0
WORKING            | copperfield / willow-fixture-reader | claude Sonnet 5.5
IDLE               | copperfield | unknown · Q:2

maple-lab · 2 queued notices
IDLE *             | ORPHAN / orphaned-birch-agent | claude Haiku 5.5
WORKING            | maple-lab / cedar-worker | codex GPT-6.1-Sol
WORKING            | maple-lab | unknown · Q:1
DONE               | maple-lab / extraordinarily-long-fictional-agent-n… | claude Opus 5.5
Registry: tests/fixtures/board-registry.json · refreshed 2026-10-19 09:19:05 PKT
```

## 60 columns

```text
ORCH BOARD · 2 projects · 3 orchs · 5 agents
Legend: ! blocked; * orphan; working; idle; done; unknown
------------------------------------------------------------
STATE              | HIERARCHY PATH
copperfield · 2 queued notices
BLOCKED !          | copperfield / blocked-spruce-worker
BLOCKED !          | copperfield-review
WORKING            | copperfield / willow-fixture-reader
IDLE               | copperfield

maple-lab · 2 queued notices
IDLE *             | ORPHAN / orphaned-birch-agent
WORKING            | maple-lab / cedar-worker
WORKING            | maple-lab
DONE               | maple-lab / extraordinarily-long-ficti…
Registry: …registry.json · refreshed 2026-10-19 09:19:05 PKT
```

## Herdr integration not verified

Installed Herdr 0.9.5 help confirms `plugin pane open` and its `--target-pane`, `--direction`, and `--cwd` options. It exposes no plugin-pane listing command. The brief prohibits opening a pane during this build, so the real open response fields and a reliable way to detect an already-open board remain unverified. `orch register` retains its existing open call; it does not inspect the open response or deduplicate an existing board pane.
