# Start cost

What each start and close path puts into an agent's context. Measured by
`scripts/measure-start.sh` (plan 2026-10-17, phase 0). Phase 5 reruns the same probe and adds
an "after" column here.

## Baseline, static (2026-10-17)

Estimate only: tokens = words x 1.3, not measured. Test home `~/.cache/orch-skill-test-home/home`
with orch 0.10.0, session-close 1.0.2, lore 1.0.0 (memory files copied from the owner's home,
no hub) and the Herdr skill from herdr 0.9.5; repo orch-skill at f87a02c (vendored KIS 0.10.1).
Two runs gave byte-identical output.

| Path | Words | Est. tokens |
|---|---:|---:|
| global:claude (CLAUDE.md, INDEX.md, repo AGENTS.md) | 1303 | 1694 |
| global:codex | 1302 | 1693 |
| global:cmd | 1303 | 1694 |
| global:agy | 1302 | 1693 |
| anchor:kis (SessionStart output) | 165 | 215 |
| kis:start (start.md, kis/state) | 442 | 575 |
| orch:start:light (SKILL.md, start.md, State) | 2676 | 3479 |
| orch:start:heavy (light + ledger template, status, watch, four references, Herdr skill) | 8659 | 11257 |
| session-close (SKILL.md, KIS sync, check) | 981 | 1275 |

The orch SKILL.md alone is 1908 words (est. 2480 tokens) and the Herdr skill 2314 words
(est. 3008).

## Baseline, live (2026-10-17)

`scripts/measure-live.py` in the same test home, headless, fixtures rebuilt per case (fictional
repos pebble-notes and tidepool-cli). Hosts: Claude Code 2.1.300 (claude-sonnet-5-5, medium),
Codex 0.162.1 (gpt-6.1-sol, medium), Command Code 1.82.5 (its configured default,
z-ai/glm-5.3-flash, default effort), agy 1.4.0 (default model). Tokens are each host's own usage
fields summed over the session, cached input included (`tokens_in`); they compare within a host
only. Raw runs: `~/.cache/orch-skill-test-home/runs/2026-10-17-baseline/` (`summary.tsv`).

Session A per case (start step plus the fix; `resume-reopen` adds the KIS sync step), tokens in:

| Host | fix | resume-clear A | resume-reopen A | no-kis |
|---|---:|---:|---:|---:|
| claude | 111,579 | 111,650 | 172,634 | 193,820 |
| codex | 239,113 | 239,695 | 247,182 | 218,153 |
| cmd | 395,754 | 314,605 | 484,985 | 1,787,614 |
| agy | 694,744 | 957,925 | not run | not run |

Session B (fresh process, start step, inventory), tokens in, and recovery against the seeded
open set T2, T3, D1, D2:

| Host | resume-clear B | resume-reopen B | Missing | T1 listed |
|---|---:|---:|---|---|
| claude | 109,908 | 110,843 | none | both, as "not committed" |
| codex | 99,473 | 122,596 | none | no |
| cmd | 186,773 | 269,146 | none | no |
| agy | 1,224,967 | not run | none | no |

Every completed session reached the fix (tests green after) and asked the owner no questions.
No session forgot an open task or decision.

Caveats:
- Deviations approved 2026-10-17: a fresh process stands in for /clear (SessionStart source
  `startup`, not `clear`); approvals cannot be counted headless, so questions to the owner are
  counted instead (lines ending in "?" in the final message).
- Claude's T1 lines say the fix is done but not committed: the prompt forbade commits, so this
  is not forgotten work. A `stale` count for phase 5 compares like with like only under the same
  prompt.
- agy's `resume-reopen` and `no-kis` hit its plan quota (429, resets about 2026-10-24); rerun
  them then with `--host agy --case resume-reopen --case no-kis`.
- The first full run (`runs/2026-10-17-run1-herdr-leak/`) is void: the XDG dirs still pointed at
  the owner's home, so test agents could reach the owner's live Herdr server (agy read one pane;
  nothing was changed). The harness now moves the XDG dirs and refuses to run while herdr reaches
  a server. The first cmd run (`runs/2026-10-17-cmd-permission-mode/`) is void too:
  `--permission-mode yolo` does not enable tools in print mode; `--yolo` does.
