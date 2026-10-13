#!/usr/bin/env bash
# Guard: no orchestrator-facing file tells the agent to read the full `herdr agent list` or
# `herdr pane list` JSON. It must go through scripts/orch-agents.sh, which returns only the
# fields it needs (about 12.6k chars a call otherwise).
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
fail() { echo "FAIL: $*" >&2; exit 1; }

roots=(
  "$repo_root/skills/orch/commands"
  "$repo_root/skills/orch/SKILL.md"
  "$repo_root/skills/orch/ledger-template.md"
  "$repo_root/skills/orch/references"
)
count=0
hits=""
while IFS= read -r -d '' f; do
  count=$((count + 1))
  if grep -qE 'herdr (agent|pane) list' "$f"; then hits="$hits $f"; fi
done < <(find "${roots[@]}" -type f -print0)

# Measured 2026-10-09: 13 files across the four roots; a scan that sees far fewer found the
# wrong tree.
[[ "$count" -ge 10 ]] || fail "scanned only $count files, expected at least 10"
[[ -z "$hits" ]] || fail "raw herdr agent/pane list read in:$hits"

# The scripts that never reach the orchestrator's context may still read the list themselves.
grep -q 'herdr agent list' "$repo_root/skills/orch/scripts/orch-agents.sh" || fail "orch-agents.sh no longer reads herdr agent list"
grep -q 'herdr agent list' "$repo_root/skills/orch/scripts/orch-model.sh" || fail "orch-model.sh no longer reads herdr agent list"
echo "ok: $count orchestrator-facing files scanned, no raw herdr agent/pane list"
