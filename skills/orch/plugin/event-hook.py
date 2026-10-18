#!/usr/bin/env python3
"""Wake signal only; the run's watcher owns delivery and signal-file truncation."""
import json
import os
from pathlib import Path
import sys
import time


def main():
    event = os.environ.get("HERDR_PLUGIN_EVENT", "")
    if event not in ("pane.agent_status_changed", "pane.closed"):
        raise ValueError("unsupported HERDR_PLUGIN_EVENT")
    payload = json.loads(os.environ.get("HERDR_PLUGIN_EVENT_JSON", "{}"))
    data = payload.get("data", {})
    pane = data.get("pane_id")
    status = data.get("agent_status")
    if not isinstance(pane, str) or not pane:
        raise ValueError("event data.pane_id missing")
    if status is not None and not isinstance(status, str):
        raise ValueError("event data.agent_status must be text or null")
    if event == "pane.closed":
        status = None
    record = {"ts": int(time.time()), "event": event, "pane": pane, "status": status}
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "orch"
    cache.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
    fd = os.open(cache / "events.signal", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if os.write(fd, line) != len(line):
            raise OSError("short signal write")
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"orch event hook: {exc}", file=sys.stderr)
        sys.exit(1)
