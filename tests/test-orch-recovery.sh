#!/usr/bin/env bash
# Fresh-session recovery mid-run: State carries the KIS 0.11 `Run:` line with an absolute path, the
# ledger carries Task and Next. A standalone KIS start (the vendored .agents/skills/kis files, used
# as text fixtures; no live host) must find the pointer. The anchor script is run for real; the
# start steps are checked as text, and their reading is replayed on the temp project.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
kis="$repo_root/.agents/skills/kis"
gate="$repo_root/skills/orch/scripts/orch-gate.py"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME"
fail() { echo "FAIL: $*" >&2; exit 1; }
has() { grep -q -F -- "$2" "$1" || fail "$(basename "$1"): missing: $2"; }

proj="$tmp/proj"; run="$tmp/rundir"
mkdir -p "$proj/kis/state" "$proj/.agents/skills" "$run"
cp -R "$kis" "$proj/.agents/skills/kis"
ledger="$run/ledger.md"
cat > "$ledger" <<LED
# Orchestrator ledger: recovery-test
Updated: 2026-10-18T10:00:00Z by w1:p1
Task: ship the fees module
Next action (w1:p1): release docs-agent after fees-agent merges
Waiting on user: none

## Pane agents
| name | owner | kind/model | pane | worktree / branch | brief | handoff | status | last event | depends | owns |
|---|---|---|---|---|---|---|---|---|---|---|
| fees-agent | w1:p1 | claude/sonnet | w1:p2 | ../r.wt/fees / fees | b.md | h.md | working | 10:00 prompted | none | src/fees/** |
| docs-agent | w1:p1 | claude/sonnet | - | ../r.wt/docs / docs | b2.md | h2.md | queued: after fees-agent | 10:01 held | fees-agent | src/fees/README.md |

## Watcher
pane w1:p3, pid 1, wakes: w1:p1, agents: fees-agent (agents.txt), log: events.log
LED
cat > "$proj/kis/state/current.md" <<STATE
# Current

- Stamp: main 0000000 deadbeef
- Branch: \`main\`.
- Run: orch run active; live record at $ledger
- Merged: setup abc1234; proof tests/run.sh: ok
STATE

# 1. the shipped anchor shows the pointer whole, with the absolute path
anchor="$("$kis/hooks/session-anchor.sh" "$proj")"
echo "$anchor" | grep -F -q -- "Run: orch run active; live record at $ledger" \
  || fail "anchor lost the Run pointer: $anchor"
# 2. the vendored start steps tell a fresh session to follow it, and to report a missing target
has "$kis/commands/start.md" 'If State has a `Run:` line, read the head (about 60 lines) of the live record it names and take Task and Next from there.'
has "$kis/commands/start.md" 'If that path does not exist, report it as a contradiction.'
has "$kis/SKILL.md" 'take the current Task and Next from it rather than from State or the conversation'
# 3. replay: the pointer parses to the ledger, whose head answers Task and Next and shows the queue
path="$(sed -n 's/^- Run: orch run active; live record at \(\/.*\)$/\1/p' "$proj/kis/state/current.md")"
[[ "$path" == /* && -f "$path" ]] || fail "pointer does not name an existing absolute path: [$path]"
head60="$(head -60 "$path")"
echo "$head60" | grep -q '^Task: ship the fees module$' || fail "ledger head lacks Task"
echo "$head60" | grep -q '^Next action (w1:p1): release docs-agent after fees-agent merges$' || fail "ledger head lacks Next"
echo "$head60" | grep -q '| queued: after fees-agent |' || fail "ledger head lacks the queued row"
# State carries no task status copied from the ledger
if grep -q -E '^- (Task|Next):' "$proj/kis/state/current.md"; then fail "State copied Task or Next"; fi
# 4. recovery while queued: the gate reads only the ledger, so a new session still holds the queued
#    task, then releases it once the blocker's row says merged
out="$(python3 "$gate" release "$run")"; [[ "$out" == 'hold docs-agent after fees-agent' ]] || fail "queued row on recovery: $out"
sed -i 's/| working |/| merged |/' "$ledger"
out="$(python3 "$gate" release "$run")"; [[ "$out" == 'release docs-agent' ]] || fail "release after merge: $out"
# 5. a pointer to a missing ledger is reported by start and flagged by check (text of the vendored steps)
has "$kis/commands/check.md" 'A `Run:` line whose live-record file does not exist is a finding.'
echo "ok: recovery"
