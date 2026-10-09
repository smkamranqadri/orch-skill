#!/bin/bash
# Kept for old ledgers and briefs: the watcher is orch-watch.py beside this file.
exec python3 "$(dirname "$0")/orch-watch.py" "$@"
