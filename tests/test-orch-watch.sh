#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# Never inherit a real Herdr session. The Python suite installs its own fake executable.
for name in $(env | sed -n 's/^\(HERDR_[^=]*\)=.*/\1/p'); do unset "$name"; done
export PYTHONDONTWRITEBYTECODE=1
python3 "$here/orch-watch-tests.py" "$@"
