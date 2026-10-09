#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
for name in $(env | sed -n 's/^\(HERDR_[^=]*\)=.*/\1/p'); do unset "$name"; done
unset CMD_API_KEY
export PYTHONDONTWRITEBYTECODE=1
python3 "$here/orch-cmd-usage-tests.py" "$@"
