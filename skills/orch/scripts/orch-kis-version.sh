#!/usr/bin/env bash
# Report the KIS version vendored in a repository and whether it can follow a `Run:` pointer.
#
#   orch-kis-version.sh [repo-path]   -> prints "kis <version>" or "kis none"
#
# Exit 0: KIS 0.11.0 or newer. Exit 3: older (offer the repo's KIS update). Exit 2: no KIS
# package in the repo (offer to install it, or use the minimal ledger).
set -euo pipefail

MIN="0.11.0"
start="${1:-$PWD}"
[[ -d "$start" ]] || { echo "Error: no such directory: $start" >&2; exit 1; }
root="$(git -C "$start" rev-parse --show-toplevel 2>/dev/null || (cd "$start" && pwd -P))"
skill="$root/.agents/skills/kis/SKILL.md"
if [[ ! -f "$skill" ]]; then
  echo "kis none"; exit 2
fi
version="$(sed -n 's/^[[:space:]]*version:[[:space:]]*"\{0,1\}\([0-9][0-9.]*\)"\{0,1\}[[:space:]]*$/\1/p' "$skill" | head -1)"
if [[ -z "$version" ]]; then
  echo "kis unknown"; exit 3
fi
echo "kis $version"
[[ "$(printf '%s\n%s\n' "$MIN" "$version" | sort -V | head -1)" == "$MIN" ]] || exit 3
