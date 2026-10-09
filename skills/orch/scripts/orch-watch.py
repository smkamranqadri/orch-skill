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

    def seed_recent(self):
        recent = []
        for l in read_lines(self.log)[-200:]:
            m = LINE.match(l)
            if m and m.group(3) in PLAIN:
                recent.append(f"{local(m.group(1))}  {m.group(2)}  {PLAIN[m.group(3)]}")
            elif m and m.group(2) == "orchestrator":
                recent.append(f"{local(m.group(1))}  → orchestrator told")
        return recent[-5:]

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

    def board(self):
        width = shutil.get_terminal_size((100, 20)).columns
        orch = (read_lines(os.path.join(self.dir, "orchestrator")) or ["none"])[0]
        out = [f"orch watcher · {os.path.basename(os.path.dirname(os.path.abspath(self.dir))).removesuffix(".reports")}"
               f" · {dt.datetime.now().strftime('%H:%M')} · {self.orch_note or 'orchestrator: ' + orch}"]
        if self.usage:
            out.append(self.usage[:width])
        out.append(f"{'AGENT':<18} {'OWNER':<14} {'STATE':<12} {'SINCE':<6} {'CONTEXT':<10} TASK")
        for name, state in self.prev.items():
            title, ctx = self.info.get(name, ("", ""))
            row = f"{name[:18]:<18} {self.owners.get(name, "none")[:14]:<14} {WORDS.get(state, state):<12} {local(self.since[name]):<6} {(ctx or '-')[:10]:<10} {title}"
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
        save_registrations(d, have + [n + (f" orch={owner}" if owner else "")
                                     for n in dict.fromkeys(names) if n not in existing])


def cmd_remove(d, names):
    with registration_lock(d):
        save_registrations(d, [line for line in read_lines(os.path.join(d, "agents.txt"))
                               if line.split()[0] not in names])


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


def cmd_orch(d, target):
    write_lines(os.path.join(d, "orchestrator"), [target])


def cmd_board(d):
    w = Watcher(d)
    live = agent_list() or {}
    w.owners = registrations(d)
    for name in w.owners:
        entry = live.get(name)
        w.prev[name] = entry.get("agent_status", "unknown") if entry else "gone"
        w.since[name] = iso()
        for l in reversed(read_lines(w.log)):
            m = LINE.match(l)
            if m and m.group(2) == name:
                w.since[name] = m.group(1)
                break
        w.info[name] = ((entry or {}).get("terminal_title_stripped", ""), context_of(name) if entry else "")
    w.refresh_usage()
    print(w.board())


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
    elif cmd == "orch" and rest:
        cmd_orch(d, rest[0])
    elif cmd == "board":
        cmd_board(d)
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
