# Phase 4 board preview

Generated on 2026-10-19 from `tests/fixtures/board-registry-crowded.json`. The registry was created in temporary Git repositories with the existing PhaseOne test harness and its fake `herdr`, by running real `orch register --name ...` commands for six orch entries and `orch spawn ...` commands for eight workers. Projects and orch names differ. All names and content are fictional.

The fake `herdr` returns newly spawned agents as working and does not generate arbitrary status transitions, orphaned owners, or queued notices. Following the test fixtures, after CLI generation the registry's `agents[*].status` values were set to cover idle, working, blocked, done, and unknown; two spawned agents' `orch` references were changed to absent registry keys to create the orphan rows; and one registered orch's `queue` received a single fictional notice. The rest of each record, including registration and spawn fields, came from the CLI.

The capture has three projects, two active orchs per project, two orphans, a long orch name, a long worker name, every requested agent status, and a queued notice.

Commands:

```sh
python3 plugin/board.py --once --width 100 --registry tests/fixtures/board-registry-crowded.json
python3 plugin/board.py --once --width 60 --registry tests/fixtures/board-registry-crowded.json
```

## 100 columns

```text
ORCH BOARD · 3 projects · 6 orchs · 8 agents
Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan
----------------------------------------------------------------------------------------------------
STATE              | HIERARCHY PATH                                                   | HOST / MODEL
fictional-amber-garden · 1 queued notice
○ IDLE *           | ORPHAN > fictional-orphan-fir-worker                             | claude
▶ WORKING          | amber-lead-orch > fictional-amber-worker                         | claude
○ IDLE             | amber-lead-orch                                                  | claude · Q:1
○ IDLE             | amber-review-orch                                                | claude · Q:0
○ IDLE             | amber-review-orch > fictional-idle-reviewer                      | claude

fictional-blue-harbor · 0 queued notices
! BLOCKED          | blue-lead-orch > fictional-blocked-builder                       | claude
○ IDLE             | blue-lead-orch                                                   | claude · Q:0
○ IDLE             | fictional-coordinator-with-an-extraordinarily-long-name          | claude · Q:0
? UNKNOWN          | fictional-coordinator-with-an-… > fictional-worker-with-an-extr… | claude

fictional-copper-hill · 0 queued notices
? UNKNOWN *        | ORPHAN > fictional-orphan-ash-worker                             | claude
▶ WORKING          | copper-review-orch > fictional-copper-reviewer                   | claude
○ IDLE             | copper-lead-orch                                                 | claude · Q:0
○ IDLE             | copper-review-orch                                               | claude · Q:0
✓ DONE             | copper-lead-orch > fictional-completed-worker                    | claude
Registry: tests/fixtures/board-registry-crowded.json · refreshed 2026-10-19 10:05:27 PKT
```

## 60 columns

```text
ORCH BOARD · 3 projects · 6 orchs · 8 agents
Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan
------------------------------------------------------------
STATE              | HIERARCHY PATH
fictional-amber-garden · 1 queued notice
○ IDLE *           | ORPHAN > fictional-orphan-fir-worker
▶ WORKING          | amber-lead-or… > fictional-amber-worker
○ IDLE             | amber-lead-orch
○ IDLE             | amber-review-orch
○ IDLE             | amber-review… > fictional-idle-reviewer

fictional-blue-harbor · 0 queued notices
! BLOCKED          | blue-lead-o… > fictional-blocked-build…
○ IDLE             | blue-lead-orch
○ IDLE             | fictional-coordinator-with-an-extraord…
? UNKNOWN          | fictional-c… > fictional-worker-with-a…

fictional-copper-hill · 0 queued notices
? UNKNOWN *        | ORPHAN > fictional-orphan-ash-worker
▶ WORKING          | copper-revi… > fictional-copper-review…
○ IDLE             | copper-lead-orch
○ IDLE             | copper-review-orch
✓ DONE             | copper-lead… > fictional-completed-wor…
Reg: tests/fixtures/board-registry-crowded.json · 10:05:27
```

## Herdr integration not verified

The live Herdr pane was not opened. The actual `plugin pane open` response, detection of an existing board pane, and a screenshot inside Herdr remain unverified. No owner panes or servers were changed.
