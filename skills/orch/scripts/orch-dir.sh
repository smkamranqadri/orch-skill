#!/usr/bin/env bash
# Print the orch run directory for a repository, creating it when needed.
#
#   orch-dir.sh [repo-path]        -> prints the dir; creates <repo>/.orch and excludes it
#   orch-dir.sh --check [repo-path] -> prints the dir that would be used; creates nothing
#
# The dir is <repo>/.orch, kept out of git through .git/info/exclude (one entry covers every
# worktree, nothing is committed). Outside a git repository, .orch under the given path.
set -euo pipefail

common=""
mode="use"
usage="usage: orch-dir.sh [--check] [repo-path]"
start=""
for arg in "$@"; do
  case "$arg" in
    --check) mode="check" ;;
    -*) echo "Error: unknown option: $arg ($usage)" >&2; exit 2 ;;
    *) [[ -z "$start" ]] || { echo "Error: more than one path: $arg ($usage)" >&2; exit 2; }
       start="$arg" ;;
  esac
done
start="${start:-$PWD}"
[[ -d "$start" ]] || { echo "Error: no such directory: $start" >&2; exit 1; }

# The run dir belongs to the repository, not to one worktree: resolve the main checkout from
# the common git dir, so a worktree and the main checkout agree on it.
if common="$(git -C "$start" rev-parse --git-common-dir 2>/dev/null)"; then
  [[ "$common" = /* ]] || common="$(cd "$start" && pwd -P)/$common"
  common="$(cd "$common" && pwd -P)"
  root="$(dirname "$common")"
else
  root="$(cd "$start" && pwd -P)"
fi
new="$root/.orch"

if [[ "$mode" = check ]]; then
  echo "$new"
else
  mkdir -p "$new"
  if [[ -d "$common" ]]; then
    mkdir -p "$common/info"
    grep -qxF '.orch/' "$common/info/exclude" 2>/dev/null || echo '.orch/' >> "$common/info/exclude"
  fi
  echo "$new"
fi
