#!/usr/bin/env python3
"""orch-watch: the orchestrator's watcher, run OUTSIDE the orchestrator session, in its own pane.

  orch-watch.py watch <dir> [agent...] [--orch <target>]
      Runs until killed (start it with: herdr pane run <pane> "python3 <this> watch <dir> ...").
      Watches every agent in <dir>/agents.txt (the agents given here are added to it), redraws a
      board in an alternate terminal buffer, appends one line per status change to <dir>/events.log, shows a
      Herdr notification when an agent finishes, needs you, or closes, and wakes the
      owner in agents.txt (bare names fall back to <dir>/orchestrator), batching per owner
      when it is idle and its
      input box is empty. Writes its pid to <dir>/watcher.pid.
  orch-watch.py add <dir> <agent>... [--orch <target>]  register agents with an owner
  orch-watch.py move <dir> <agent>... --from <old> --orch <new>  transfer only owned agents
  orch-watch.py remove <dir> <agent>...   stop watching agents
  orch-watch.py mark <dir> <agent> <tier> "<what>" [--proof <path>]
                                          record the orchestrator's verdict in events.log; tiers:
                                          reported verified asserted sent-back merged open closed
                                          handoff (see references/visibility.md)
  orch-watch.py orch <dir> <target>       set the orchestrator to wake (agent name or pane id);
                                          "none" turns waking off
  orch-watch.py board <dir>               print the board once and exit
  orch-watch.py input <target>            what is really typed in an agent's input box: "empty",
                                          "typed: <text>" or "none" (dim suggestions and known
                                          placeholders are not typed text); use this, not a plain
                                          pane read, before saying an agent has input waiting
  orch-watch.py --next <dir> [seconds]    foreground wait until events.log grows (default 540);
                                          prints the new lines, exit 3 on timeout
"""
import datetime as dt
import fcntl
from contextlib import contextmanager
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

POLL = 4               # seconds between polls of `herdr agent list`
USAGE_EVERY = 300      # seconds between usage refreshes (orch-usage.py collect; codex is one app-server call)
RETRY = 30             # seconds between wake attempts while the orchestrator is busy or typing
HOLD_NOTICE = 120      # seconds a held wake waits before the user gets a notification
WAKE_STATES = {"done", "blocked", "gone"}
WORDS = {
    "working": "● working",
    "done": "✓ finished",
    "idle": "○ idle",
    "blocked": "! needs you",
    "unknown": "? unknown",
    "gone": "✗ closed",
}
PLAIN = {
    "working": "started working",
    "done": "finished",
    "idle": "went idle",
    "blocked": "needs you (approval or question)",
    "unknown": "state unknown",
    "gone": "pane closed",
}
LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (\S+) (\S+)")
TIERS = ("reported", "verified", "asserted", "sent-back", "merged", "open", "closed", "handoff")
EVENT = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (\S+) (.*)$")
STATE_TAIL = re.compile(r"^(working|done|idle|blocked|unknown|gone) \| (.*) \| ctx (\S.*)$")
MARK_TAIL = re.compile(r"^mark:([a-z-]+) a(\d+) \| (.*) \| proof (\S.*)$")
WOKEN_TAIL = re.compile(r"^woken(?: \(file\))?(?: orch=(\S+))? \| (.*)$")
START_TAIL = re.compile(r"^start pid (\d+) agents:(.*)$")
OWNED_TAIL = re.compile(r"^(registered|moved) orch=(\S+)$")


def parse_event(line):
    """One events.log line as a dict, or None when it is not in the log's grammar."""
    m = EVENT.match(line)
    if not m:
        return None
    stamp, agent, tail = m.groups()
    try:
        t = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    e = {"t": t, "stamp": stamp, "agent": agent}
    if (m := STATE_TAIL.match(tail)):
        e.update(kind="state", state=m.group(1), title=m.group(2), ctx=m.group(3))
    elif (m := MARK_TAIL.match(tail)):
        if m.group(1) not in TIERS:
            return None
        e.update(kind="mark", tier=m.group(1), attempt=int(m.group(2)), what=m.group(3), proof=m.group(4))
    elif agent == "orchestrator" and (m := WOKEN_TAIL.match(tail)):
        e.update(kind="woken", owner=m.group(1), agents=[a.strip() for a in m.group(2).split(",") if a.strip()])
    elif agent == "watcher" and (m := START_TAIL.match(tail)):
        e.update(kind="watcher", pid=int(m.group(1)))
    elif (m := OWNED_TAIL.match(tail)):
        e.update(kind=m.group(1), owner=m.group(2))
    elif tail == "removed":
        e.update(kind="removed")
    else:
        return None
    return e


def parse_log(d):
    """(events, bad): every parsed event in file order, and (line number, text) for each line
    outside the grammar (hand-written lines, a date with no time zone, a lone word)."""
    events, bad = [], []
    try:
        with open(os.path.join(d, "events.log")) as f:
            for n, raw in enumerate(f, 1):
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                e = parse_event(line)
                if e:
                    e["n"] = n
                    events.append(e)
                else:
                    bad.append((n, line))
    except OSError:
        pass
    return events, bad


def attempt_of(events, agent):
    """1 plus the sent-back marks since the agent's last registered line."""
    n = 1
    for e in events:
        if e["agent"] != agent:
            continue
        if e["kind"] == "registered":
            n = 1
        elif e["kind"] == "mark" and e["tier"] == "sent-back":
            n += 1
    return n


def herdr(*args, timeout=15):
    try:
        r = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def agent_list():
    code, out = herdr("agent", "list")
    if code != 0:
        return None
    try:
        agents = json.loads(out)["result"]["agents"]
    except (ValueError, KeyError, TypeError):
        return None
    found = {}
    for a in agents:
        found[a.get("pane_id")] = a
        if a.get("name"):
            found[a["name"]] = a
    return found


def pane_tail(target, n=8):
    code, out = herdr("agent", "read", target, "--source", "visible")
    if code != 0:
        return []
    return [l for l in out.splitlines() if l.strip()][-n:]


def context_of(target):
    text = " ".join(pane_tail(target))
    m = re.search(r"ctx\s+[▓░]*\s*([\d.]+[kM]?/[\d.]+[kM])", text)
    if m:
        return m.group(1)
    m = re.search(r"Context (\d+)% used", text)
    return f"{m.group(1)}% used" if m else ""


DIM = re.compile(r"\x1b\[2m.*?(?=\x1b\[(?:0|22)?m|$)")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Command Code's input placeholder is not dim: it is drawn in a grey truecolor run behind a
# reverse-video cursor, so DIM does not remove it. Match the known placeholder out by name.
PLACEHOLDER = re.compile(r"^(Ask your question|Ask Codex to anything|Type a message|Send a message)\b", re.I)


def input_empty(target):
    """True when the input box is empty, False when text is typed, None if no input box is seen.

    Claude and Codex both draw their placeholder suggestions dim, so dim text is dropped first;
    Command Code's placeholder is matched by name, see PLACEHOLDER."""
    code, out = herdr("agent", "read", target, "--source", "visible", "--ansi")
    if code != 0:
        return None
    for line in reversed([l for l in out.splitlines() if l.strip()][-14:]):
        text = ANSI.sub("", DIM.sub("", line)).replace("\xa0", " ").strip()
        if text[:1] in ("❯", "›"):
            rest = text[1:].strip()
            if PLACEHOLDER.match(rest):
                rest = ""
            return not rest
    return None


def typed_text(target):
    """The real text in the input box, '' when empty, None if no input box is seen (see input_empty)."""
    code, out = herdr("agent", "read", target, "--source", "visible", "--ansi")
    if code != 0:
        return None
    for line in reversed([l for l in out.splitlines() if l.strip()][-14:]):
        text = ANSI.sub("", DIM.sub("", line)).replace("\xa0", " ").strip()
        if text[:1] in ("❯", "›"):
            rest = text[1:].strip()
            return "" if PLACEHOLDER.match(rest) else rest
    return None


def iso(t=None):
    return dt.datetime.fromtimestamp(t or time.time(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local(stamp):
    try:
        t = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        return t.astimezone().strftime("%H:%M")
    except ValueError:
        return stamp[:5]


def read_lines(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        return []


def write_lines(path, lines):
    with open(path, "w") as f:
        f.write("".join(l + "\n" for l in lines))


UTC = dt.timezone.utc
FINISHED_AFTER = dt.timedelta(minutes=10)   # a finish with no mark, or a report not verified
UNCLOSED_AFTER = dt.timedelta(minutes=30)   # a verified or merged agent neither closed nor kept open
NEEDS_LINES = 5
EVID = {"verified": "◆ verified", "reported": "◇ reported", "asserted": "! asserted",
        "merged": "⇢ merged", "closed": "✓ closed", "open": "○ open"}


def now_utc():
    return dt.datetime.now(UTC)


def at_stamp(stamp):
    try:
        return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def mark_words(e):
    tier = "sent back" if e["tier"] == "sent-back" else e["tier"]
    return f"{local(e['stamp'])}  {e['agent']} {tier}: {e['what']}"


def life(events, name):
    """The events of one agent since its last registered line (a re-registered agent starts over)."""
    own = [e for e in events if e["agent"] == name]
    for i in range(len(own) - 1, -1, -1):
        if own[i]["kind"] == "registered":
            return own[i:]
    return own


def last_mark(events, name):
    marks = [e for e in life(events, name) if e["kind"] == "mark"]
    return marks[-1] if marks else None


def finish_of(own):
    """The latest finish in an agent's life: a `done` line, or `idle` after working or blocked."""
    finish, prev = None, None
    for e in own:
        if e["kind"] != "state":
            continue
        if e["state"] == "done" or (e["state"] == "idle" and prev in ("working", "blocked")):
            finish = e
        prev = e["state"]
    return finish


def is_held(own):
    """An `open` mark holds the not-closed rules off until the agent's next state line."""
    marks = [e for e in own if e["kind"] == "mark"]
    if not marks or marks[-1]["tier"] != "open":
        return False
    return not any(e["kind"] == "state" and e["n"] > marks[-1]["n"] for e in own)


def evidence_of(events, name):
    mark = last_mark(events, name)
    if not mark:
        return ""
    if mark["tier"] == "sent-back":
        return f"↩ a{mark['attempt']}"
    return EVID.get(mark["tier"], "")


def ago(delta):
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes}m" if minutes < 120 else f"{minutes // 60}h{minutes % 60:02d}m"


def ledger_waiting(d):
    try:
        with open(os.path.join(d, "ledger.md")) as f:
            for line in f:
                m = re.match(r"^Waiting on user:\s*(.*)$", line.strip())
                if m:
                    text = m.group(1).strip()
                    return None if not text or text.lower().rstrip(".") == "none" else text
    except OSError:
        pass
    return None


def needs_you(events, owners, live_state, since, now, wake_held=(), waiting=None, usage=""):
    """The Needs-you lines, oldest first: [(time or None, text)]. Pure over the log, so a restarted
    watcher shows the same block. Only the latest mark counts: a later `open` or `closed` mark
    is what holds the verified/merged rule off. `wake_held` is [(time, owner, count)]; `since` maps blocked
    agents to the time they started waiting."""
    items = []
    for name in owners:
        own = life(events, name)
        states = [e for e in own if e["kind"] == "state"]
        marks = [e for e in own if e["kind"] == "mark"]
        if live_state.get(name) == "blocked":
            items.append((since.get(name) or now, f"{name} is blocked and needs you"))
            continue
        flagged = False
        finish = finish_of(own)
        if finish and states and states[-1]["state"] in ("done", "idle"):
            unmarked = not any(e["n"] > finish["n"] for e in marks)
            if unmarked and now - finish["t"] >= FINISHED_AFTER:
                items.append((finish["t"], f"{name} finished {ago(now - finish['t'])} ago, no verdict marked"))
                flagged = True
        if marks and not flagged:
            tier, t = marks[-1]["tier"], marks[-1]["t"]
            if tier == "reported" and now - t >= FINISHED_AFTER:
                items.append((t, f"{name} reported {ago(now - t)} ago, not verified"))
            elif tier in ("verified", "merged") and now - t >= UNCLOSED_AFTER:
                items.append((t, f"{name} {tier} {ago(now - t)} ago, not closed (close it or mark open)"))
    for t, owner, count in wake_held:
        items.append((t, f"{count} wake(s) held for {owner}"))
    items.sort(key=lambda x: x[0])
    if waiting:
        items.append((None, f"waiting on user: {waiting}"))
    asked = [seg.split()[0] for seg in usage.split(" · ") if seg.split() and "ASK" in seg.split()]
    if asked:
        items.append((None, f"usage ASK: {', '.join(asked)}"))
    return items


class Watcher:
    def __init__(self, d):
        self.dir = d
        self.log = os.path.join(d, "events.log")
        self.prev = {}        # agent -> state
        self.seq = {}         # agent -> completion_seq, which catches a turn shorter than a poll
        self.since = {}       # agent -> iso time of last change
        self.info = {}        # agent -> (title, ctx)
        self.pending = []     # (iso, agent, state) waiting to be told to the orchestrator
        self.held_since = {}
        self.held_noticed = {}
        self.next_try = {}
        self.recent = self.seed_recent()
        self.orch_note = ""
        self.owners = {}
        self.owner_notes = {}
        self.last_board = None
        self.usage = ""       # one line from orch-usage.py, refreshed every USAGE_EVERY seconds
        self.usage_at = 0
        self.clock = now_utc

    def seed_recent(self):
        recent = []
        for l in read_lines(self.log)[-200:]:
            m = LINE.match(l)
            e = parse_event(l)
            if e and e["kind"] == "mark":
                recent.append(mark_words(e))
            elif m and m.group(3) in PLAIN:
                recent.append(f"{local(m.group(1))}  {m.group(2)}  {PLAIN[m.group(3)]}")
            elif m and m.group(2) == "orchestrator":
                recent.append(f"{local(m.group(1))}  → orchestrator told")
        try:
            self.log_pos = os.path.getsize(self.log)
        except OSError:
            self.log_pos = 0
        return recent[-5:]

    def read_marks(self):
        """Marks are written by the orchestrator's `mark` command, not by this process: tail the log."""
        try:
            with open(self.log, "rb") as f:
                f.seek(self.log_pos)
                chunk = f.read()
        except OSError:
            return False
        end = chunk.rfind(b"\n") + 1
        self.log_pos += end
        changed = False
        for raw in chunk[:end].decode(errors="replace").splitlines():
            e = parse_event(raw)
            if e and e["kind"] == "mark":
                self.recent = (self.recent + [mark_words(e)])[-5:]
                changed = True
        return changed

    def append(self, line):
        with open(self.log, "a") as f:
            f.write(line + "\n")

    def notify(self, title, body):
        herdr("notification", "show", title, "--body", body[:120], "--sound", "done")

    def refresh_usage(self):
        if time.time() - self.usage_at < USAGE_EVERY:
            return False
        self.usage_at = time.time()
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orch-usage.py")
        try:
            subprocess.run([sys.executable, script, "collect"], capture_output=True, text=True, timeout=45)
            r = subprocess.run([sys.executable, script, "line"], capture_output=True, text=True, timeout=10)
            new = r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            new = ""
        changed = new != self.usage
        self.usage = new
        return changed

    def poll(self):
        live = agent_list()
        if live is None:
            return False
        changed = self.refresh_usage()
        changed |= self.read_marks()
        self.owners = registrations(self.dir)
        names = self.owners
        for name in names:
            entry = live.get(name)
            state = entry.get("agent_status", "unknown") if entry else "gone"
            seq = (entry or {}).get("completion_seq")
            finished = seq is not None and name in self.seq and seq != self.seq[name]
            if seq is not None:
                self.seq[name] = seq
            if finished and state != "working":
                state = "done" if state in ("idle", "done") else state
                self.prev[name] = None  # log this finish even if the state looks unchanged
            if state == self.prev.get(name):
                continue
            first = name not in self.prev
            if first and seq is not None:
                self.seq[name] = seq
            now = iso()
            title = (entry or {}).get("terminal_title_stripped", "") or self.info.get(name, ("", ""))[0]
            ctx = context_of(name) if entry else ""
            self.info[name] = (title, ctx)
            self.since[name] = now
            before = self.prev.get(name)
            self.prev[name] = state
            changed = True
            self.append(f"{now} {name} {state} | {title} | ctx {ctx or '-'}")
            if {before, state} != {"done", "idle"}:  # done <-> idle is only the user looking at the pane
                self.recent = (self.recent + [f"{local(now)}  {name}  {PLAIN.get(state, state)}"])[-5:]
            if first:
                continue
            wake = state in WAKE_STATES or (state == "idle" and before in ("working", "blocked"))
            if wake:
                self.pending.append((now, name, state))
                self.notify(f"{name}: {PLAIN.get(state, state)}", title or state)
        for name in list(self.prev):
            if name not in names:
                del self.prev[name]
                self.seq.pop(name, None)
                self.info.pop(name, None)
                self.since.pop(name, None)
                changed = True
        if self.pending:
            changed |= self.try_wake(live)
        elif self.orch_note:
            self.orch_note = ""
            changed = True
        return changed

    def try_wake(self, live):
        # Resolve at delivery time: pending events follow agents through a handoff.
        self.owners = registrations(self.dir)
        self.pending = [e for e in self.pending if e[1] in self.owners]
        changed = False
        notes = []
        for target in dict.fromkeys(self.owners[a] for _, a, _ in self.pending):
            batch = [e for e in self.pending if self.owners[e[1]] == target]
            changed |= self.wake_owner(live, target, batch)
            self.owner_notes[target] = self.owner_note
            notes.append(self.owner_note)
        note = "; ".join(notes)
        changed |= note != self.orch_note
        self.orch_note = note
        return changed

    def wake_owner(self, live, target, batch):
        self.owner_note = self.owner_notes.get(target, f"wakes {target}")
        if target == "none":
            self.owner_note = "waking off"
            return False
        if time.time() < self.next_try.get(target, 0):
            return False
        self.next_try[target] = time.time() + RETRY
        entry = live.get(target)
        if not entry:
            note = f"orchestrator {target} not found; {len(batch)} event(s) held"
        else:
            st = entry.get("agent_status")
            empty = input_empty(target)
            safe = empty is True or (empty is None and not entry.get("focused"))
            if st not in ("idle", "done"):
                note = f"orchestrator {target} {st}; {len(batch)} event(s) held until it is idle"
            elif not safe:
                note = f"orchestrator {target} has typed input or is focused; {len(batch)} event(s) held"
            else:
                parts = [f"{a} {PLAIN.get(s, s)} ({local(t)})" for t, a, s in batch[-6:]]
                more = len(batch) - 6
                text = "orch event: " + "; ".join(parts) + (f"; and {more} more" if more > 0 else "")
                text += ". Follow ~/.agents/skills/orch/commands/event.md."
                code, _ = herdr("agent", "prompt", target, text, "--wait", "--until", "working",
                                "--timeout", "8000", timeout=20)
                if code != 0:
                    # A harness Herdr can observe but not drive (Command Code): `agent prompt`
                    # refuses it ("not an active named agent") and a prompt typed into its composer
                    # is never submitted, so put the wake where the orchestrator will read it at
                    # the start of its next turn instead of typing it into the pane.
                    who = ", ".join(sorted({a for _, a, _ in batch}))
                    try:
                        with open(os.path.join(self.dir, "wake.md"), "a") as f:
                            f.write(f"- {iso()} orch={target}  {text}\n")
                    except OSError as exc:
                        self.owner_note = f"could not write wake.md: {exc}"
                        return True
                    self.append(f"{iso()} orchestrator woken (file) orch={target} | {who}")
                    self.delivered(target, batch)
                    self.owner_note = f"wake written to wake.md for {target}"
                    return True
                if code == 0:
                    now = iso()
                    who = ", ".join(sorted({a for _, a, _ in batch}))
                    self.append(f"{now} orchestrator woken orch={target} | {who}")
                    self.recent = (self.recent + [f"{local(now)}  → {target} told: {who}"])[-5:]
                    self.delivered(target, batch)
                    self.owner_note = f"wakes {target}"
                    return True
                note = f"prompt to {target} failed; retrying in {RETRY}s"
        if target not in self.held_since:
            self.held_since[target] = time.time()
        if not self.held_noticed.get(target) and time.time() - self.held_since[target] > HOLD_NOTICE:
            self.notify("orchestrator: events waiting", note)
            self.held_noticed[target] = True
        changed = note != self.owner_note
        self.owner_note = note
        return changed

    def delivered(self, target, batch):
        self.pending = [e for e in self.pending if e not in batch]
        self.held_since.pop(target, None)
        self.held_noticed.pop(target, None)

    def wake_held(self):
        out = []
        for target, t0 in self.held_since.items():
            count = sum(1 for e in self.pending if self.owners.get(e[1]) == target)
            if count:
                out.append((dt.datetime.fromtimestamp(t0, UTC), target, count))
        return out

    def board(self, now=None):
        width = shutil.get_terminal_size((100, 20)).columns
        now = now or self.clock()
        events, _ = parse_log(self.dir)
        orch = (read_lines(os.path.join(self.dir, "orchestrator")) or ["none"])[0]
        out = [f"orch watcher · {os.path.basename(os.path.dirname(os.path.abspath(self.dir))).removesuffix(".reports")}"
               f" · {dt.datetime.now().strftime('%H:%M')} · {self.orch_note or 'orchestrator: ' + orch}"]
        if self.usage:
            out.append(self.usage[:width])
        since = {n: at_stamp(t) for n, t in self.since.items()}
        items = needs_you(events, self.owners, self.prev, since, now, self.wake_held(),
                          ledger_waiting(self.dir), self.usage)
        if items:
            out.append(f"NEEDS YOU ({len(items)})")
            for t, text in items[:NEEDS_LINES]:
                out.append(("  " + (local(t.strftime("%Y-%m-%dT%H:%M:%SZ")) + " " if t else "") + text)[:width])
            if len(items) > NEEDS_LINES:
                out.append(f"  +{len(items) - NEEDS_LINES} more")
        out.append(f"{'AGENT':<16} {'OWNER':<8} {'STATE':<11} {'EVID':<10} {'SINCE':<5} {'CONTEXT':<9} TASK")
        for name, state in self.prev.items():
            title, ctx = self.info.get(name, ("", ""))
            row = (f"{name[:16]:<16} {self.owners.get(name, 'none')[:8]:<8} {WORDS.get(state, state):<11} "
                   f"{evidence_of(events, name):<10} {local(self.since[name]):<5} {(ctx or '-')[:9]:<9} {title}")
            out.append(row[:width])
        if not self.prev:
            out.append("(no agents; add with: orch-watch.py add <dir> <agent>)")
        out.append("")
        out.append("Recent")
        out.extend(("  " + r)[:width] for r in self.recent)
        return "\n".join(out)

    def draw(self):
        board = self.board()
        if board == self.last_board:
            return
        self.last_board = board
        sys.stdout.write("\033[H\033[2J" + board + "\n")
        sys.stdout.flush()


def cmd_watch(d, args):
    orch = None
    if "--orch" in args:
        i = args.index("--orch")
        orch = args[i + 1]
        args = args[:i] + args[i + 2:]
    os.makedirs(d, exist_ok=True)
    if args:
        cmd_add(d, args + (["--orch", orch] if orch else []))
    if orch and not read_lines(os.path.join(d, "orchestrator")):
        cmd_orch(d, orch)
    with open(os.path.join(d, "watcher.pid"), "w") as f:
        f.write(f"{os.getpid()}\n")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    w = Watcher(d)
    w.append(f"{iso()} watcher start pid {os.getpid()} agents: {' '.join(read_lines(os.path.join(d, 'agents.txt')))}")
    terminal = sys.stdout.isatty()
    try:
        if terminal:
            sys.stdout.write("\033[?1049h\033[?25l")
            sys.stdout.flush()
        while True:
            w.poll()
            w.draw()
            time.sleep(POLL)
    finally:
        if terminal:
            sys.stdout.write("\033[?25h\033[?1049l")
            sys.stdout.flush()


@contextmanager
def registration_lock(d):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "agents.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def default_owner(d):
    return (read_lines(os.path.join(d, "orchestrator")) or ["none"])[0]


def registrations(d):
    default = default_owner(d)
    result = {}
    for line in read_lines(os.path.join(d, "agents.txt")):
        fields = line.split()
        if len(fields) not in (1, 2) or (len(fields) == 2 and not fields[1].startswith("orch=")):
            raise ValueError(f"invalid agent registration: {line}")
        result[fields[0]] = fields[1][5:] if len(fields) == 2 else default
    return result


def owner_option(args):
    args = list(args)
    owner = None
    if "--orch" in args:
        i = args.index("--orch")
        owner = args[i + 1]
        if not owner or len(owner.split()) != 1 or owner.startswith("--"):
            raise ValueError("expected a single owner target")
        del args[i:i + 2]
    if not args or any(n.startswith("--") or len(n.split()) != 1 for n in args):
        raise ValueError("expected agent names")
    return args, owner


def save_registrations(d, lines):
    path = os.path.join(d, "agents.txt")
    temporary = path + ".tmp"
    write_lines(temporary, lines)
    os.replace(temporary, path)


def cmd_add(d, args):
    names, owner = owner_option(args)
    with registration_lock(d):
        have = read_lines(os.path.join(d, "agents.txt"))
        existing = {line.split()[0] for line in have}
        # Existing registrations retain their owner; use guarded move for reassignment.
        new = [n for n in dict.fromkeys(names) if n not in existing]
        save_registrations(d, have + [n + (f" orch={owner}" if owner else "") for n in new])
        for n in new:  # a re-add of a registered name is a no-op and must not reset its attempts
            log_append(d, f"{iso()} {n} registered orch={owner or default_owner(d)}")


def cmd_remove(d, names):
    with registration_lock(d):
        have = read_lines(os.path.join(d, "agents.txt"))
        save_registrations(d, [line for line in have if line.split()[0] not in names])
        for n in dict.fromkeys(names):
            if any(line.split()[0] == n for line in have):
                log_append(d, f"{iso()} {n} removed")


def cmd_move(d, args):
    args = list(args)
    i = args.index("--from")
    old = args[i + 1]
    del args[i:i + 2]
    names, owner = owner_option(args)
    if not owner:
        raise ValueError("move requires --orch <new>")
    with registration_lock(d):
        have = registrations(d)
        if any(n not in have or have[n] != old for n in names):
            raise ValueError("move refused: missing agent or owner differs from --from")
        lines = read_lines(os.path.join(d, "agents.txt"))
        save_registrations(d, [f"{line.split()[0]} orch={owner}"
                               if line.split()[0] in names else line for line in lines])
        for n in dict.fromkeys(names):  # `moved`, never `registered`: a handoff keeps the attempt count
            log_append(d, f"{iso()} {n} moved orch={owner}")


def log_append(d, line):
    with open(os.path.join(d, "events.log"), "a") as f:
        f.write(line + "\n")


def cmd_mark(d, args):
    args = list(args)
    proof = "-"
    if "--proof" in args:
        i = args.index("--proof")
        if i + 1 >= len(args):
            raise ValueError("--proof needs a path")
        proof = " ".join(args[i + 1].split()) or "-"
        del args[i:i + 2]
    if len(args) != 3:
        raise ValueError('usage: mark <dir> <agent> <tier> "<what>" [--proof <path>]')
    agent, tier, what = args
    if not agent or len(agent.split()) != 1 or agent.startswith("--"):
        raise ValueError("expected one agent name")
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; tiers: {' '.join(TIERS)}")
    what = " ".join(what.split()).replace(" | ", " / ")
    if not what:
        raise ValueError("a mark needs a reason or result in words")
    os.makedirs(d, exist_ok=True)
    events, _ = parse_log(d)
    n = attempt_of(events, agent) + (1 if tier == "sent-back" else 0)  # a sent-back mark is the attempt it opens
    log_append(d, f"{iso()} {agent} mark:{tier} a{n} | {what} | proof {proof}")


def cmd_orch(d, target):
    write_lines(os.path.join(d, "orchestrator"), [target])


def cmd_board(d, now=None):
    w = Watcher(d)
    live = agent_list() or {}
    w.owners = registrations(d)
    for name in w.owners:
        entry = live.get(name)
        w.prev[name] = entry.get("agent_status", "unknown") if entry else "gone"
        w.since[name] = iso()
        for l in reversed(read_lines(w.log)):
            m = LINE.match(l)
            if m and m.group(2) == name and m.group(3) in PLAIN:  # state lines only: marks do not move SINCE
                w.since[name] = m.group(1)
                break
        w.info[name] = ((entry or {}).get("terminal_title_stripped", ""), context_of(name) if entry else "")
    w.refresh_usage()
    print(w.board(now))


def option_now(args):
    """`--now <ISO>` pins the clock (tests, and rendering a board at a known time)."""
    if "--now" in args:
        stamp = args[args.index("--now") + 1]
        t = at_stamp(stamp)
        if not t:
            raise ValueError("--now expects 2026-10-13T10:00:00Z")
        return t
    return None


def cmd_next(d, secs):
    log = os.path.join(d, "events.log")
    open(log, "a").close()
    start = sum(1 for _ in open(log))
    deadline = time.time() + secs
    while time.time() < deadline:
        lines = open(log).read().splitlines()
        if len(lines) > start:
            print("\n".join(lines[start:]))
            return 0
        time.sleep(5)
    return 3


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, d, rest = argv[0], argv[1], argv[2:]
    if cmd == "input":
        t = typed_text(d)
        print("none" if t is None else ("empty" if t == "" else f"typed: {t}"))
    elif cmd == "watch":
        cmd_watch(d, rest)
    elif cmd == "add" and rest:
        cmd_add(d, rest)
    elif cmd == "remove" and rest:
        cmd_remove(d, rest)
    elif cmd == "move" and rest:
        cmd_move(d, rest)
    elif cmd == "mark" and rest:
        cmd_mark(d, rest)
    elif cmd == "orch" and rest:
        cmd_orch(d, rest[0])
    elif cmd == "board":
        cmd_board(d, option_now(rest))
    elif cmd == "--next":
        return cmd_next(d, int(rest[0]) if rest else 540)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, IndexError) as exc:
        print(f"orch-watch: {exc}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(0)
