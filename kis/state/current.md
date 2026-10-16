# Current

- Branch: `main`, in step with `origin/main` (public). Source: orch 0.10.0, session-close 1.0.2,
  vendored KIS 0.10.1. No code change since 43eed48.
- Machine: fresh Linux laptop (2026-10). orch and session-close are **not installed** here. In
  `~/.agents/skills`, linked for Claude and agy: lore 1.0.0 (from lore-skill), herdr (upstream
  `herdrdev/herdr` 143bf5f) and humanizer (upstream `blader/humanizer` 3.1.0). The earlier setup
  and its `.orch/` proof logs stay on the owner's other machine.
- Task: none open. Session 2026-10-16 did the landscape research (doc "Agent Stack Landscape
  Report", https://claude.ai/code/artifact/461cac36-c255-4f21-b056-fe80a896c54f) and built and
  released lore 1.0.0 in `../lore-skill` (its own State holds the proof).
- Blocker: none.
- Command: `tests/run.sh`; `ORCH_TEST_NO_LIVE=1` skips live Codex probes;
  `./bootstrap.sh check --source .`.
- Next (new session, owner's call): plan the KIS and orch changes deferred until lore was done.
  Owner's stance (2026-10-16): KIS works well, change it only after discussion (hooks or skills
  that cut ceremony are welcome); orch is early, heavily used and open to the best design; a
  small project uses KIS alone, a big one uses orch, which works without KIS or offers to install
  it. Every host (Claude Code, Codex, Command Code, agy) keeps the same layer.
  1. orch `start`/`handoff` and session-close still call `/lore:load` and `/lore:retro`; lore
     1.0.0 loads through each agent's global file and captures on its own, so those steps change.
  2. One front door: `kis:start` decides the work mode and escalates to orch for many agents.
  3. orch slimming from the research: native host hooks and Monitor, or agent-of-empires,
     instead of parts of the watcher; keep the ledger, evidence tiers and usage-based CLI choice.
  4. Then install orch and session-close on this machine.
- Open from before: placement table against research cases, multi-owner successor wake, real
  marks end to end, watcher restart finish-age, cmd cache keeping the last reading after a failed
  fetch, full-permission starts, the parked Tartib run migration. The rules-split branch of
  2026-10-14 is not on this machine.
