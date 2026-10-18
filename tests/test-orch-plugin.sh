#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
for name in $(env | sed -n 's/^\(HERDR_[^=]*\)=.*/\1/p'); do unset "$name"; done
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
export HOME="$scratch/home" XDG_CACHE_HOME="$scratch/cache" PYTHONDONTWRITEBYTECODE=1
unset ORCH_RUN_DIR ORCH_USAGE_CACHE_DIR
mkdir -p "$HOME"
python3 "$here/orch-plugin-tests.py" "$@"
