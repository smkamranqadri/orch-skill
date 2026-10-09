#!/usr/bin/env bash
# Guard: no shipped file names the retired agent-lessons skill or its /lessons: commands.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { echo "FAIL: $*" >&2; exit 1; }

count=0
hits=""
while IFS= read -r -d '' f; do
  count=$((count + 1))
  if grep -qE 'agent-lessons|/lessons:' "$f"; then hits="$hits $f"; fi
done < <(find "$repo_root/skills" -type f -print0)

# measured 2026-10-09: 19 files under skills/; a scan that sees far fewer found the wrong tree
[[ "$count" -ge 15 ]] || fail "scanned only $count files under skills/, expected at least 15"
[[ -z "$hits" ]] || fail "retired lessons reference in:$hits"
echo "ok: $count files under skills/ scanned, no agent-lessons or /lessons: reference"
