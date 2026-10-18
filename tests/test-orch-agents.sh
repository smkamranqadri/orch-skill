#!/usr/bin/env bash
# Guard: orch-agents.sh prints only the compact fields the orchestrator asked for, never the
# full Herdr JSON, and its exit codes let a caller test for a live target.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$repo_root/skills/orch/scripts/orch-agents.sh"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

cat > "$tmp/agents.json" <<'J'
{"id":"cli:agent:list","result":{"agents":[
 {"name":"worker-cmd","agent":"cmd","pane_id":"w1:p1","agent_status":"working",
  "display_agent":"cmd · deepseek/deepseek-v4-flash","tokens":{"model":"deepseek/deepseek-v4-flash"},
  "cwd":"/repo/wt/fees","terminal_title_stripped":"fees","completion_seq":7,"focused":false},
 {"name":"review","agent":"codex","pane_id":"w1:p3","agent_status":"idle","tokens":null,
  "cwd":"/repo/wt/review","completion_seq":2,"terminal_title_stripped":"review"},
 {"name":"code","agent":"claude","pane_id":"w1:p2","agent_status":"done",
  "tokens":{},"cwd":"/repo/wt/code","completion_seq":1}
]}}
J
cat > "$tmp/panes.json" <<'J'
{"id":"cli:pane:list","result":{"panes":[
 {"pane_id":"w1:p1","label":"cmd","cwd":"/repo/wt/fees","agent":"cmd","terminal_title_stripped":"fees"},
 {"pane_id":"w1:p9","label":"watcher","cwd":"/repo/wt","agent":null}
]}}
J
export ORCH_AGENTS_FIXTURE_LIST="$tmp/agents.json"
export ORCH_AGENTS_FIXTURE_PANES="$tmp/panes.json"

out="$("$S")"
[[ "$out" == name*pane*status*model*cwd* ]] || fail "header missing: $out"
[[ "$out" == *"worker-cmd"*"w1:p1"*"working"*"deepseek/deepseek-v4-flash"*"/repo/wt/fees"* ]] || fail "worker row wrong: $out"
[[ "$out" == *"review"*"w1:p3"*"idle"*"-"*"/repo/wt/review"* ]] || fail "review row (no model -> -) wrong: $out"
# The compact output must not carry any raw JSON key or value shape.
for k in tokens agent_status completion_seq terminal_title_stripped display_agent focused; do
  [[ "$out" != *"$k"* ]] || fail "raw JSON key leaked: $k"
done
[[ "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" == "4" ]] || fail "expected 4 lines (header + 3 agents)"
[[ "$(printf '%s\n' "$out" | sed -n '2p')" == code* ]] || fail "rows not sorted by name: $out"

# --fields asks for a subset, in the given order.
out="$("$S" --fields status,name)"
[[ "$out" == "status"*"name"* ]] || fail "--fields order ignored: $out"
[[ "$out" == *"working  worker-cmd"* ]] || fail "--fields row wrong: $out"
if [[ "$out" == *"deepseek"* || "$out" == *"/repo/"* ]]; then fail "--fields leaked an unrequested field"; fi

# A named target filters to one entry; a missing one exits 2 with empty stdout.
out="$("$S" worker-cmd)"
[[ "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" == "2" ]] || fail "target should print header + 1 row: $out"
[[ "$out" == *"worker-cmd"* && "$out" != *"review"* ]] || fail "target filter wrong: $out"
set +e; out="$("$S" --fields name nobody 2>"$tmp/e")"; rc=$?; set -e
[[ $rc -eq 2 ]] || fail "missing target should exit 2, got $rc"
[[ -z "$out" ]] || fail "missing target printed stdout: $out"
grep -q "no live agent" "$tmp/e" || fail "missing target message absent"

# Panes mode projects the pane fields only.
out="$("$S" --panes)"
[[ "$out" == pane*label*cwd*agent* ]] || fail "panes header wrong: $out"
[[ "$out" == *"w1:p9"*"watcher"* ]] || fail "watcher pane missing: $out"
out="$("$S" --panes watcher)"
[[ "$out" == *"w1:p9"* && "$out" != *"w1:p1"* ]] || fail "pane target filter wrong: $out"

# Usage errors and an unreadable live list.
set +e; "$S" --fields bogus >/dev/null 2>&1; rc=$?; set -e
[[ $rc -eq 64 ]] || fail "unknown field should exit 64, got $rc"
set +e; "$S" --nope >/dev/null 2>&1; rc=$?; set -e
[[ $rc -eq 64 ]] || fail "unknown option should exit 64, got $rc"
set +e; ORCH_AGENTS_FIXTURE_LIST="$tmp/absent.json" "$S" >/dev/null 2>&1; rc=$?; set -e
[[ $rc -eq 3 ]] || fail "unreadable list should exit 3, got $rc"

# The whole point: the projection is far smaller than the source JSON.
src_bytes="$(wc -c < "$tmp/agents.json" | tr -d ' ')"
out_bytes="$("$S" | wc -c | tr -d ' ')"
[[ "$out_bytes" -lt "$src_bytes" ]] || fail "projection ($out_bytes) not smaller than source ($src_bytes)"

# Live, read-only, only inside Herdr with agents.
unset ORCH_AGENTS_FIXTURE_LIST ORCH_AGENTS_FIXTURE_PANES
if [[ -z "${ORCH_TEST_NO_LIVE:-}" && "${HERDR_ENV:-}" == "1" ]] && command -v herdr >/dev/null 2>&1; then
  full_bytes="$(herdr agent list 2>/dev/null | wc -c | tr -d ' ')"
  live_bytes="$("$S" | wc -c | tr -d ' ')"
  [[ "$live_bytes" -lt "$full_bytes" ]] || fail "live projection ($live_bytes) not smaller than herdr ($full_bytes)"
  echo "(live: herdr agent list $full_bytes chars -> orch-agents $live_bytes chars)"
fi
echo "orch-agents tests: pass"
