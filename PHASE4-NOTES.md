# Phase 4 board preview

Generated on 2026-10-19 from `tests/fixtures/board-registry-cli.json`, written by the Phase 1 CLI test harness (`register`, then `spawn fictional-worker`). The project (`repo`) and orch (`orch`) names differ. The fixture retains the CLI's recorded orch fields, including `kind`, `workspace`, and `tab`.

Commands:

```sh
python3 plugin/board.py --once --width 100 --registry tests/fixtures/board-registry-cli.json
python3 plugin/board.py --once --width 60 --registry tests/fixtures/board-registry-cli.json
```

## 100 columns

```text
ORCH BOARD · 1 projects · 1 orchs · 1 agents
Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan
----------------------------------------------------------------------------------------------------
STATE              | HIERARCHY PATH                                     | HOST / MODEL
repo · 0 queued notices
▶ WORKING          | repo > orch > fictional-worker                     | claude
○ IDLE             | repo > orch                                        | claude · Q:0
Registry: tests/fixtures/board-registry-cli.json · refreshed 2026-10-19 09:38:31 PKT
```

## 60 columns

```text
ORCH BOARD · 1 projects · 1 orchs · 1 agents
Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan
------------------------------------------------------------
STATE              | HIERARCHY PATH
repo · 0 queued notices
▶ WORKING          | repo > orch > fictional-worker
○ IDLE             | repo > orch
Reg: tests/fixtures/board-registry-cli.json · 09:38:31
```

## Herdr integration not verified

The live Herdr pane was not opened. The actual `plugin pane open` response, detection of an existing board pane, and a screenshot inside Herdr remain unverified. No owner panes or servers were changed.
