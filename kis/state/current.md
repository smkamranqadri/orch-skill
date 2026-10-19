# Current

Stamp: main e702c3c b9625144bfc7

- Branch: `main`, local only, not pushed (`origin/main` is far behind). Branches `board-v2`
  (`7dcbfee`) and `phase3-board-design` (`d944922`) deleted 2026-10-19 (recover from the reflog or
  those SHAs while unpruned). No other branches or worktrees; the build agents
  are closed. The old 0.12.2 build is gone from the tree (history `613aa67`); ideas worth keeping
  are in `kis/intent/ideas-from-0.12.2.md`.
- Task: plan `kis/intent/plan-2026-10-18-orch-v1.md`, Mode Phase. Phases 1-6 built and merged.
  Phase 5 (skill plus the notice cap) was reviewed once; its 1 P1 + 2 P2 were fixed and not
  re-reviewed. Phase 6 (installer, README, CI) was reviewed once; its 2 P1 + 6 P2 were fixed and
  not re-reviewed, then a live installer `check` bug (Herdr's real `plugin_root` field) was fixed.
- Blocker: none.
- Command: `./tests/run.sh` (169 tests, passing on `main`, 2026-10-19).
- Proof: suites re-run by the orchestrator on `main` after every merge. Live (2026-10-19): hook,
  worker spawn and notice delivery to an idle orch; `orch adopt`; real install from the checkout
  (`./bootstrap.sh install --source .`) and `check` pass, skill copy at `~/.agents/skills/orch`
  with Claude Code and Codex links, `orch` on PATH, plugin linked to this checkout (not a GitHub
  install, nothing pushed). Reviewers: Codex gpt-6.1-sol medium; builder GPT-6-Luna.
- Not verified live: `orch:*` commands in a fresh Claude Code and Codex session (repo with KIS and
  scratch repo without, planner spawn, close asking before removing a worktree), the cap on a real
  clock (`orch resume`, `[cap] prompts_per_hour`), `prefix+b` overlay closing on `q`, a worktree
  spawn after the flag fix, the GitHub release install path, GitHub Actions, macOS and Bash 3.2.
  Duplicate notices are coalesced by a guard; the root cause is unknown (needs the raw event
  payloads of one worker run).
- Next: (1) owner live checks above. (2) Before any push: review every outgoing commit and the
  full diff (123+ commits; authors `T <t@example.invalid>` and the owner's address). The owner
  pushes and tags; the stale remote branch goes with `git push origin --delete orch-0.12.2`.
  (3) Parked: the herdrctx-style board (dropped with `board-v2`; its review found a missing title
  lookup timeout, a fixed 8-column Project, titles ignoring the session prefix, flat agent rows),
  row select-and-enter, the idea list.
  Owner decision 2026-10-19: no more builder/reviewer loops for now.
