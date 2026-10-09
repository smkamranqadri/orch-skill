#!/usr/bin/env bash
# Print the orch run directory for a repository, creating it when needed.
#
#   orch-dir.sh [repo-path]        -> prints the dir; creates <repo>/.orch and excludes it
#   orch-dir.sh --check [repo-path] -> prints the dir that would be used; creates nothing
#
# Rules: a legacy run at ../<repo>.reports/orch/ledger.md wins while it exists, so an old run
# is never given a second, empty ledger (migrate it by hand or with --migrate). Otherwise the
# dir is <repo>/.orch, kept out of git through .git/info/exclude (one entry covers every
# worktree, nothing is committed). Outside a git repository, .orch under the given path.
#
#   orch-dir.sh --migrate [repo-path] -> moves the legacy dir into <repo>/.orch (refuses when
#                                       both exist) and prints the new dir
set -euo pipefail

common=""
mode="use"
case "${1:-}" in
  --check) mode="check"; shift ;;
  --migrate) mode="migrate"; shift ;;
esac
start="${1:-$PWD}"
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
name="$(basename "$root")"
legacy="$(dirname "$root")/$name.reports/orch"
new="$root/.orch"

exclude_new() {
  [[ -d "${common:-}" ]] || return 0
  mkdir -p "$common/info"
  grep -qxF '.orch/' "$common/info/exclude" 2>/dev/null || echo '.orch/' >> "$common/info/exclude"
}

case "$mode" in
  check)
    if [[ -f "$legacy/ledger.md" && ! -f "$new/ledger.md" ]]; then
      echo "$legacy"; echo "legacy run; migrate with: orch-dir.sh --migrate $root" >&2
    else
      echo "$new"
    fi
    ;;
  use)
    if [[ -f "$legacy/ledger.md" && ! -f "$new/ledger.md" ]]; then
      echo "$legacy"
      echo "legacy run at $legacy; .orch not created. Migrate with: orch-dir.sh --migrate $root" >&2
    else
      mkdir -p "$new"
      exclude_new
      echo "$new"
    fi
    ;;
  migrate)
    [[ -d "$legacy" ]] || { echo "Error: no legacy dir at $legacy" >&2; exit 1; }
    if [[ -e "$new" ]] && [[ -n "$(ls -A "$new" 2>/dev/null)" ]]; then
      echo "Error: $new already exists and is not empty; merge by hand" >&2; exit 1
    fi
    rmdir "$new" 2>/dev/null || true
    mv "$legacy" "$new"
    exclude_new
    # agent folders (briefs, reports) live beside the old orch dir: move them too
    parent="$(dirname "$legacy")"
    for d in "$parent"/*/; do
      [[ -d "$d" ]] || continue
      mv "$d" "$new/$(basename "$d")"
    done
    rmdir "$parent" 2>/dev/null || echo "note: $parent kept (not empty)" >&2
    echo "$new"
    ;;
esac
