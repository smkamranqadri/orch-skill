#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$repo_root/skills/orch/scripts/orch-model.sh"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

cat > "$tmp/list.json" <<'J'
{"id":"cli:agent:list","result":{"agents":[
 {"name":"worker-cmd","agent":"cmd","pane_id":"w1:p1","display_agent":"cmd · deepseek/deepseek-v4-flash","tokens":{"model":"deepseek/deepseek-v4-flash"}},
 {"name":"fresh-cmd","agent":"cmd","pane_id":"w1:p5","tokens":{}},
 {"name":"code","agent":"claude","pane_id":"w1:p2","display_agent":null,"tokens":{}},
 {"name":"review","agent":"codex","pane_id":"w1:p3","tokens":null},
 {"name":"blank","agent":"claude","pane_id":"w1:p4"}
]}}
J
export ORCH_MODEL_FIXTURE_LIST="$tmp/list.json"
printf 'Working on the fees screen\n\xe2\x9d\xaf \n  Sonnet 5.5 \xc2\xb7 ctx \xe2\x96\x93\xe2\x96\x91 92k/1M\n' > "$tmp/claude.txt"
printf 'OpenAI Codex (v0.162.0)\nmodel: GPT-6.1-Sol medium\n\xe2\x80\xba \n' > "$tmp/codex.txt"
printf 'nothing here\n' > "$tmp/empty.txt"

# cmd: model from the list, match and mismatch
out="$(ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" worker-cmd)"; [[ "$out" == "kind=cmd model=deepseek/deepseek-v4-flash" ]] || fail "cmd read: $out"
ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" worker-cmd deepseek/deepseek-v4-flash >/dev/null || fail "cmd match should pass"
ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" worker-cmd DEEPSEEK-v4-flash >/dev/null || fail "cmd match should be case-insensitive"
if ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" worker-cmd sonnet >"$tmp/o" 2>"$tmp/e"; then fail "cmd mismatch should exit 1"; fi
grep -q MISMATCH "$tmp/e" || fail "mismatch not reported"

# Before the first turn, Command Code shows the unqualified model with its latest suffix.
printf 'deepseek-v4-flash-(latest)\n' > "$tmp/fresh.txt"
out="$(ORCH_MODEL_FIXTURE_PANE="$tmp/fresh.txt" "$S" fresh-cmd)"
[[ "$out" == "kind=cmd model=deepseek-v4-flash-(latest)" ]] || fail "fresh cmd read: $out"
for expected in deepseek/deepseek-v4-flash deepseek-v4-flash deepseek/deepseek-v4-flash-\(latest\); do
  ORCH_MODEL_FIXTURE_PANE="$tmp/fresh.txt" "$S" fresh-cmd "$expected" >/dev/null || fail "fresh cmd match: $expected"
done
ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" worker-cmd deepseek-v4-flash-\(latest\) >/dev/null || fail "list model should ignore expected latest suffix"
printf 'deepseek-v4-pro-(latest)\n' > "$tmp/pro.txt"
if ORCH_MODEL_FIXTURE_PANE="$tmp/pro.txt" "$S" fresh-cmd deepseek/deepseek-v4-flash >"$tmp/o" 2>"$tmp/e"; then fail "fresh cmd pro must mismatch flash"; fi
grep -q MISMATCH "$tmp/e" || fail "fresh mismatch not reported"
if ORCH_MODEL_FIXTURE_PANE="$tmp/fresh.txt" "$S" fresh-cmd deepseek-v4-flash-extra >/dev/null 2>&1; then fail "different full model must mismatch"; fi
if ORCH_MODEL_FIXTURE_PANE="$tmp/fresh.txt" "$S" fresh-cmd deepseek-v4 >/dev/null 2>&1; then fail "partial full model must mismatch"; fi

# claude: model from pane text; pane id works as target too
out="$(ORCH_MODEL_FIXTURE_PANE="$tmp/claude.txt" "$S" code)"; [[ "$out" == "kind=claude model=Sonnet 5.5" ]] || fail "claude read: $out"
ORCH_MODEL_FIXTURE_PANE="$tmp/claude.txt" "$S" w1:p2 sonnet >/dev/null || fail "claude match by pane id"
ORCH_MODEL_FIXTURE_PANE="$tmp/claude.txt" "$S" code opus >/dev/null 2>&1 && fail "claude mismatch should fail" || true

# codex
out="$(ORCH_MODEL_FIXTURE_PANE="$tmp/codex.txt" "$S" review)"; [[ "$out" == "kind=codex model=GPT-6.1-Sol medium" ]] || fail "codex read: $out"
ORCH_MODEL_FIXTURE_PANE="$tmp/codex.txt" "$S" review gpt-6.1-sol >/dev/null || fail "codex match"
if ORCH_MODEL_FIXTURE_PANE="$tmp/codex.txt" "$S" review gpt-6-astra >/dev/null 2>&1; then fail "codex mismatch should fail"; fi

# not visible -> exit 2; unknown agent -> exit 2
set +e
ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" blank sonnet >/dev/null 2>&1; rc=$?; set -e
[[ $rc -eq 2 ]] || fail "not visible should exit 2, got $rc"
set +e
ORCH_MODEL_FIXTURE_PANE="$tmp/empty.txt" "$S" nobody sonnet >/dev/null 2>&1; rc=$?; set -e
[[ $rc -eq 2 ]] || fail "unknown agent should exit 2, got $rc"

# live, read-only, only inside Herdr with a cmd agent present
unset ORCH_MODEL_FIXTURE_LIST
if [[ "${HERDR_ENV:-}" == "1" ]] && command -v herdr >/dev/null 2>&1; then
  live="$(herdr agent list 2>/dev/null | python3 -I -c 'import json,sys
for a in json.load(sys.stdin)["result"]["agents"]:
    if a.get("agent")=="cmd" and a.get("name"): print(a["name"]); break' || true)"
  if [[ -n "$live" ]]; then
    "$S" "$live" deepseek >/dev/null || fail "live cmd agent $live should run deepseek"
    if "$S" "$live" sonnet >/dev/null 2>&1; then fail "live mismatch should fail"; fi
    echo "(live check on $live: pass)"
  fi
fi
echo "orch-model tests: pass"
