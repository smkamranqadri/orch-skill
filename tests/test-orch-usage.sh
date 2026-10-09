#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
U="$repo_root/skills/orch/scripts/orch-usage.py"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
export ORCH_USAGE_CACHE_DIR="$tmp/cache"; unset CMD_API_KEY
fail() { echo "FAIL: $*" >&2; exit 1; }
now=$(date +%s)
PY="$(command -v python3)"

# 1. nothing cached: every CLI unknown, check exits 2
out="$(python3 "$U" collect --cached)"
grep -q "^claude unknown" <<<"$out" || fail "claude should be unknown: $out"
grep -q "^codex  unknown" <<<"$out" || fail "codex should be unknown: $out"
grep -q "^cmd    unknown.*CMD_API_KEY" <<<"$out" || fail "cmd should ask for the key: $out"
set +e; python3 "$U" check claude >/dev/null; rc=$?; set -e; [[ $rc -eq 2 ]] || fail "check unknown should exit 2, got $rc"

# 2. claude cache from the statusline shape; codex cached reading; thresholds
mkdir -p "$tmp/cache"
cat > "$tmp/cache/usage-claude.json" <<J
{"cli":"claude","fetched_at":$((now-120)),"model":"Sonnet 5.5","rate_limits":{"five_hour":{"used_percentage":41.7,"resets_at":$((now+3600))},"seven_day":{"used_percentage":83.2,"resets_at":$((now+86400))}}}
J
cat > "$tmp/cache/usage-codex.json" <<J
{"cli":"codex","status":"ok","fetched_at":$((now-60)),"plan":"plus","five_hour":{"used_pct":23,"resets_at":$((now+5000))},"seven_day":{"used_pct":28,"resets_at":$((now+400000))}}
J
out="$(python3 "$U" collect --cached)"
grep -q "^claude 5h 42% (resets .*)  7d 83% (resets .*)  as of 2m ago" <<<"$out" || fail "claude line: $out"
grep -q "ASK the user before starting a task on claude: 83% used" <<<"$out" || fail "claude warning missing: $out"
grep -q "^codex  5h 23% (resets .*)  7d 28%" <<<"$out" || fail "codex line: $out"
grep -q "ASK the user before starting a task on codex" <<<"$out" && fail "codex should not warn" || true
line="$(python3 "$U" line)"
[[ "$line" == "usage claude 42%/83% ASK · codex 23%/28% · cmd ?" ]] || fail "line: $line"
set +e; python3 "$U" check claude >/dev/null; rc=$?; set -e; [[ $rc -eq 3 ]] || fail "claude check should exit 3, got $rc"
python3 "$U" check codex >/dev/null || fail "codex check should exit 0"
test -f "$tmp/cache/usage.json" || fail "combined cache not written"

# 3. a fresh codex reading is reused (no app-server start) even without --cached
before=$(stat -f %m "$tmp/cache/usage-codex.json" 2>/dev/null || stat -c %Y "$tmp/cache/usage-codex.json")
PATH="$tmp/nobin" "$PY" "$U" collect >/dev/null 2>&1 || fail "collect with fresh codex cache should not need the codex binary"
after=$(stat -f %m "$tmp/cache/usage-codex.json" 2>/dev/null || stat -c %Y "$tmp/cache/usage-codex.json")
[[ "$before" == "$after" ]] || fail "fresh codex cache was rewritten"

# 4. a stale codex reading with no codex binary stays as the last known value, not an error
python3 - "$tmp/cache/usage-codex.json" <<'P'
import json,sys,time
p=sys.argv[1]; d=json.load(open(p)); d["fetched_at"]=int(time.time())-900; json.dump(d,open(p,"w"))
P
out="$(PATH="$tmp/nobin" "$PY" "$U" collect 2>&1)" || fail "collect without codex binary exited non-zero"
grep -q "^codex  5h 23%" <<<"$out" || fail "stale reading should be kept when codex is absent: $out"

# 5. live, read-only: only when codex is installed and logged in; one app-server call
if command -v codex >/dev/null 2>&1 && [[ -z "${ORCH_TEST_NO_LIVE:-}" ]]; then
  rm -f "$tmp/cache/usage-codex.json"
  out="$(python3 "$U" collect 2>&1)" || fail "live collect failed: $out"
  if grep -q "^codex  5h [0-9]*%" <<<"$out"; then echo "(live codex reading: ok)"; else echo "(live codex reading unavailable: $(grep '^codex' <<<"$out"))"; fi
fi
echo "orch-usage tests: pass"
