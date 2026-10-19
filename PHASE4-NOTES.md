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
STATE              | HIERARCHY PATH                                     | HOST / MODEL
fictional-amber-garden · 1 queued notices
○ IDLE *           | fictional… > ORPHAN > fictional-orphan-fir-worker  | claude
▶ WORKING          | fictional-… > amber-lead… > fictional-amber-worker | claude
○ IDLE             | fictional-amber-garden > amber-lead-orch           | claude · Q:1
○ IDLE             | fictional-amber-garden > amber-review-orch         | claude · Q:0
○ IDLE             | fictional… > amber-revi… > fictional-idle-reviewer | claude

fictional-blue-harbor · 0 queued notices
! BLOCKED          | fictional… > blue-lead… > fictional-blocked-build… | claude
○ IDLE             | fictional-blue-harbor > blue-lead-orch             | claude · Q:0
○ IDLE             | fictional-blue-harbor > fictional-coordinator-wit… | claude · Q:0
? UNKNOWN          | fictional… > fictional… > fictional-worker-with-a… | claude

fictional-copper-hill · 0 queued notices
? UNKNOWN *        | fictional… > ORPHAN > fictional-orphan-ash-worker  | claude
▶ WORKING          | fictional… > copper-re… > fictional-copper-review… | claude
○ IDLE             | fictional-copper-hill > copper-lead-orch           | claude · Q:0
○ IDLE             | fictional-copper-hill > copper-review-orch         | claude · Q:0
✓ DONE             | fictional… > copper-le… > fictional-completed-wor… | claude
Registry: tests/fixtures/board-registry-crowded.json · refreshed 2026-10-19 09:51:57 PKT
```

## 60 columns

```text
ORCH BOARD · 3 projects · 6 orchs · 8 agents
Legend: ○ idle ▶ work ! blocked ✓ done ? unknown * orphan
------------------------------------------------------------
STATE              | HIERARCHY PATH
fictional-amber-garden · 1 queued notices
○ IDLE *           | fic… > ORPH… > fictional-orphan-fir-wo…
▶ WORKING          | fict… > amber… > fictional-amber-worker
○ IDLE             | fictional-amber-gard… > amber-lead-orch
○ IDLE             | fictional-amber-ga… > amber-review-orch
○ IDLE             | fict… > ambe… > fictional-idle-reviewer

fictional-blue-harbor · 0 queued notices
! BLOCKED          | fic… > blue… > fictional-blocked-build…
○ IDLE             | fictional-blue-harbor > blue-lead-orch
○ IDLE             | fictional-b… > fictional-coordinator-w…
? UNKNOWN          | fic… > fict… > fictional-worker-with-a…

fictional-copper-hill · 0 queued notices
? UNKNOWN *        | fic… > ORPH… > fictional-orphan-ash-wo…
▶ WORKING          | fic… > copp… > fictional-copper-review…
○ IDLE             | fictional-copper-hi… > copper-lead-orch
○ IDLE             | fictional-copper-… > copper-review-orch
✓ DONE             | fic… > copp… > fictional-completed-wor…
Reg: tests/fixtures/board-registry-crowded.json · 09:51:57
```

## Herdr integration not verified

The live Herdr pane was not opened. The actual `plugin pane open` response, detection of an existing board pane, and a screenshot inside Herdr remain unverified. No owner panes or servers were changed.
