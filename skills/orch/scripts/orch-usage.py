#!/usr/bin/env python3
"""orch-usage: how much of each CLI's plan is used (5-hour and weekly windows), for the board.

  orch-usage.py collect [--cached]   refresh the readings and print them (``--cached``: files only,
                                     no CLI is started); writes <cache>/usage.json
  orch-usage.py show                 one line per CLI from the last collect, plus warnings
  orch-usage.py line                 one compact line for the ledger header and the watcher board
  orch-usage.py check <kind>         refresh, then exit 0 when <kind> is under the ask threshold,
                                     3 when at or above it (the orchestrator asks the user
                                     first), 2 unknown (``--cached``: files only)

Sources (this script only reads; `task` chooses the kind with usage available, and asks the user when unclear):
  claude  ~/.cache/orch/usage-claude.json, written by the owner's Claude Code statusline command
          from the statusline JSON (rate_limits.five_hour / seven_day). Needs one Claude session
          to have answered since the window changed; the file's age is shown.
  codex   `codex app-server` over stdio: initialize, then account/rateLimits/read
          (windowDurationMins 300 = 5-hour, 10080 = weekly). Refreshed at most every 5 minutes.
  cmd     Command Code has no official usage command. With CMD_API_KEY in the environment the
          unofficial https://api.commandcode.ai/alpha/billing/credits is read (field names from
          the cmd-usage crate, unverified here); the key is never printed and auth.json is never
          read. Without the key: unknown.
Cache dir: $ORCH_USAGE_CACHE_DIR, else $XDG_CACHE_HOME/orch, else ~/.cache/orch.
"""
import datetime as dt
import json
import os
import select
import subprocess
import sys
import time
import urllib.request

ASK_AT = 80            # percent used in either window: the orchestrator asks before a new task
CODEX_MAX_AGE = 300    # seconds a codex reading is reused before the app-server is asked again
CLIS = ("claude", "codex", "cmd")


def cache_dir():
    d = os.environ.get("ORCH_USAGE_CACHE_DIR") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "orch")
    os.makedirs(d, exist_ok=True)
    return d


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def window(used, resets_at):
    return {"used_pct": None if used is None else round(float(used)), "resets_at": resets_at}


def read_claude(d):
    raw = load(os.path.join(d, "usage-claude.json"))
    if not raw or not raw.get("rate_limits"):
        return {"cli": "claude", "status": "unknown", "note": "no statusline cache yet (needs one Claude session to answer)"}
    rl = raw["rate_limits"]
    fh, sd = rl.get("five_hour") or {}, rl.get("seven_day") or {}
    return {"cli": "claude", "status": "ok", "fetched_at": raw.get("fetched_at"),
            "five_hour": window(fh.get("used_percentage"), fh.get("resets_at")),
            "seven_day": window(sd.get("used_percentage"), sd.get("resets_at"))}


def codex_rpc(timeout=25):
    p = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    try:
        def send(obj):
            p.stdin.write(json.dumps(obj) + "\n"); p.stdin.flush()

        def recv(want_id):
            end = time.time() + timeout
            while time.time() < end:
                r, _, _ = select.select([p.stdout], [], [], 0.5)
                if not r:
                    continue
                line = p.stdout.readline()
                if not line:
                    return None
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if msg.get("id") == want_id and ("result" in msg or "error" in msg):
                    return msg
            return None
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "orch-usage", "version": "0.1"}}})
        if not recv(1):
            return None
        send({"id": 2, "method": "account/rateLimits/read", "params": {}})
        return recv(2)
    finally:
        p.terminate()


def read_codex(d, cached):
    path = os.path.join(d, "usage-codex.json")
    old = load(path)
    if cached or (old and time.time() - old.get("fetched_at", 0) < CODEX_MAX_AGE):
        return old or {"cli": "codex", "status": "unknown", "note": "no cached reading"}
    try:
        resp = codex_rpc()
    except OSError as exc:
        return old or {"cli": "codex", "status": "unknown", "note": f"codex not runnable: {exc}"}
    if not resp or "error" in resp:
        return old or {"cli": "codex", "status": "unknown", "note": "app-server gave no rate limits (not logged in with ChatGPT?)"}
    snap = (resp.get("result") or {}).get("rateLimits") or {}
    out = {"cli": "codex", "status": "ok", "fetched_at": int(time.time()), "plan": snap.get("planType")}
    for key in ("primary", "secondary"):
        w = snap.get(key) or {}
        mins = w.get("windowDurationMins")
        slot = "five_hour" if mins == 300 else "seven_day" if mins == 10080 else None
        if slot:
            out[slot] = window(w.get("usedPercent"), w.get("resetsAt"))
    save(path, out)
    return out


def read_cmd(d, cached):
    key = os.environ.get("CMD_API_KEY")
    path = os.path.join(d, "usage-cmd.json")
    old = load(path)
    if not key:
        return {"cli": "cmd", "status": "unknown", "note": "set CMD_API_KEY to read Command Code usage (unofficial API)"}
    if cached:
        return old or {"cli": "cmd", "status": "unknown", "note": "no cached reading"}
    req = urllib.request.Request("https://api.commandcode.ai/alpha/billing/credits",
                                 headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as exc:  # the endpoint is unofficial; any failure is just "unknown"
        return old or {"cli": "cmd", "status": "unknown", "note": f"billing endpoint failed: {type(exc).__name__}"}
    wl = data.get("windowLimits") or {}
    out = {"cli": "cmd", "status": "ok", "fetched_at": int(time.time())}
    for src, slot in (("fiveHour", "five_hour"), ("weekly", "seven_day")):
        w = wl.get(src) or {}
        used, cap = w.get("used"), w.get("cap")
        pct = None if not cap else 100.0 * float(used or 0) / float(cap)
        out[slot] = window(pct, w.get("resetAt"))
    save(path, out)
    return out


def collect(cached=False):
    d = cache_dir()
    all_ = {"collected_at": int(time.time()),
            "claude": read_claude(d), "codex": read_codex(d, cached), "cmd": read_cmd(d, cached)}
    save(os.path.join(d, "usage.json"), all_)
    return all_


def last():
    return load(os.path.join(cache_dir(), "usage.json")) or {}


def when(ts):
    if not ts:
        return "?"
    t = dt.datetime.fromtimestamp(int(ts)).astimezone()
    now = dt.datetime.now().astimezone()
    return t.strftime("%H:%M") if t.date() == now.date() else t.strftime("%a %H:%M")


def age(ts):
    if not ts:
        return ""
    s = int(time.time() - int(ts))
    return f"{s // 60}m ago" if s < 3600 else f"{s // 3600}h ago"


def fmt(entry, long=True):
    cli = entry.get("cli", "?")
    if entry.get("status") != "ok":
        return f"{cli:<7}unknown" + (f"  ({entry.get('note')})" if long and entry.get("note") else "")
    parts = []
    for slot, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = entry.get(slot)
        if w and w.get("used_pct") is not None:
            parts.append(f"{label} {w['used_pct']}%" + (f" (resets {when(w.get('resets_at'))})" if long else ""))
    s = f"{cli:<7}" + "  ".join(parts) if parts else f"{cli:<7}no windows"
    if long:
        s += f"  as of {age(entry.get('fetched_at'))}"
    return s


def worst(entry):
    if entry.get("status") != "ok":
        return None
    vals = [entry[s]["used_pct"] for s in ("five_hour", "seven_day") if entry.get(s) and entry[s].get("used_pct") is not None]
    return max(vals) if vals else None


def show(data):
    lines = []
    for cli in CLIS:
        e = data.get(cli) or {"cli": cli, "status": "unknown"}
        lines.append(fmt(e))
        w = worst(e)
        if w is not None and w >= ASK_AT:
            lines.append(f"        ASK the user before starting a task on {cli}: {w}% used")
    return "\n".join(lines)


def line(data):
    bits = []
    for cli in CLIS:
        e = data.get(cli) or {"cli": cli, "status": "unknown"}
        if e.get("status") != "ok":
            bits.append(f"{cli} ?")
            continue
        w5 = (e.get("five_hour") or {}).get("used_pct")
        w7 = (e.get("seven_day") or {}).get("used_pct")
        s = f"{cli} " + "/".join(f"{v}%" for v in (w5, w7) if v is not None)
        if (worst(e) or 0) >= ASK_AT:
            s += " ASK"
        bits.append(s)
    return "usage " + " · ".join(bits)


def main(argv):
    if not argv:
        print(__doc__); return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "collect":
        print(show(collect(cached="--cached" in rest))); return 0
    if cmd == "show":
        print(show(last())); return 0
    if cmd == "line":
        print(line(last())); return 0
    if cmd == "check" and rest:
        # Refresh first: claude is a file read and codex reuses a reading under five minutes
        # old, so a fresh orchestrator cannot start a task on a CLI at 88% because no watcher
        # has collected yet.
        e = (collect(cached="--cached" in rest).get(rest[0]) or {})
        w = worst(e)
        if w is None:
            print(f"{rest[0]}: usage unknown"); return 2
        print(f"{rest[0]}: {w}% used" + (" (at or above the ask threshold)" if w >= ASK_AT else ""))
        return 3 if w >= ASK_AT else 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
