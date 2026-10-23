#!/usr/bin/env python3
"""Render the orch registry in a live, read-only terminal board."""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path


ANSI_RE = re.compile(r"\033\[[0-9;]*m")
CONTROL_SEQUENCE_RE = re.compile(r"\033(?:\[[0-?]*[ -/]*[@-~]|\][^\a]*(?:\a|\033\\))")
BOARD_VERSION = "1.0.1"
REFRESH_SECONDS = 1
STATUS_ORDER = {"blocked": 0, "closing": 1, "cleanup": 1, "working": 2, "idle": 3, "done": 3, "unknown": 3, "closed": 4}
STATUS_GLYPHS = {"blocked": "!", "closing": "◷", "cleanup": "…", "working": "▶", "idle": "○", "done": "✓", "unknown": "?", "closed": "×"}
STATUS_COLORS = {"blocked": "blocked", "closing": "amber", "cleanup": "amber", "not-started": "amber", "working": "working", "idle": "dim", "done": "done", "unknown": "amber", "closed": "dim"}
STATE_WIDTH = 18
MIN_PATH_WIDTH = 14
MIN_OWNER_WIDTH = 6
MIN_WORKER_WIDTH = 20
MIN_WORKER_PATH_WIDTH = MIN_OWNER_WIDTH + 3 + MIN_WORKER_WIDTH
MIN_RUNTIME_WIDTH = len("HOST / MODEL")
MAX_RUNTIME_WIDTH = 26
CLOSED_ROW_SECONDS = 600


COLOR_16 = {
    "app": "1;34", "orch": "1;34", "agent": "35", "header": "1;37", "orphan": "1;33",
    "dim": "2;37", "working": "32", "done": "32", "blocked": "1;31", "purple": "35",
    "amber": "33", "key": "1;37",
}
COLOR_256 = {"app": 111, "orch": 111, "agent": 140, "header": 255, "orphan": 179, "dim": 244,
             "working": 114, "done": 114, "blocked": 167, "purple": 141, "amber": 179, "key": 255}
COLOR_RGB = {"app": (130, 156, 255), "orch": (130, 156, 255), "agent": (186, 151, 221),
             "header": (224, 228, 237), "orphan": (218, 176, 82), "dim": (112, 119, 135),
             "working": (137, 202, 132), "done": (137, 202, 132), "blocked": (231, 105, 105),
             "purple": (190, 139, 222), "amber": (218, 176, 82), "key": (222, 226, 236)}


def color(value: str, code: str, enabled: bool, mode: str = "16") -> str:
    if not enabled:
        return value
    if code not in COLOR_16:
        return f"\033[{code}m{value}\033[0m"
    if mode == "truecolor":
        red, green, blue = COLOR_RGB[code]
        ansi = f"1;38;2;{red};{green};{blue}" if code in ("app", "orch", "header", "key", "orphan") else f"38;2;{red};{green};{blue}"
    elif mode == "256":
        ansi = f"1;38;5;{COLOR_256[code]}" if code in ("app", "orch", "header", "key", "orphan") else f"38;5;{COLOR_256[code]}"
    else:
        ansi = COLOR_16[code]
    return f"\033[{ansi}m{value}\033[0m"


def terminal_color_mode(environ: dict[str, str] | None = None) -> str:
    environ = os.environ if environ is None else environ
    colorterm = environ.get("COLORTERM", "").lower()
    term = environ.get("TERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    if "256color" in term:
        return "256"
    return "16"


def display_width(value: str) -> int:
    value = ANSI_RE.sub("", value)
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in value)


def truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if display_width(value) <= limit:
        return value
    if limit == 1:
        return "…"
    result = ""
    used = 0
    active_style = False
    clipped = False
    for token in re.split(r"(\033\[[0-9;]*m)", value):
        if not token:
            continue
        if ANSI_RE.fullmatch(token):
            result += token
            active_style = token != "\033[0m"
            continue
        for char in token:
            char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
            if used + char_width > limit - 1:
                clipped = True
                break
            result += char
            used += char_width
        if clipped:
            break
    result += "…"
    if active_style:
        result += "\033[0m"
    return result


def registry_path() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "orch" / "registry.json"


def pane_titles_from_payload(payload: dict) -> dict[str, str]:
    result = payload.get("result", {})
    panes = result.get("panes", []) if isinstance(result, dict) else []
    if not isinstance(panes, list):
        return {}
    session = os.environ.get("HERDR_SESSION")
    if not session:
        return {}
    titles = {}
    for pane in panes:
        if not isinstance(pane, dict) or pane.get("pane_id") is None:
            continue
        title = pane.get("terminal_title_stripped") or pane.get("label") or pane.get("terminal_title") or ""
        titles[f"{session}/{pane['pane_id']}"] = sanitize_title(str(title))
    return titles


def sanitize_title(value: str) -> str:
    value = CONTROL_SEQUENCE_RE.sub("", value)
    return "".join(char for char in value if not unicodedata.category(char).startswith("C") and char not in "\u2028\u2029")


def read_pane_titles() -> dict[str, str]:
    try:
        response = subprocess.run(["herdr", "pane", "list"], text=True, capture_output=True, check=False, timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if response.returncode != 0:
        return {}
    try:
        payload = json.loads(response.stdout)
    except (TypeError, json.JSONDecodeError):
        return {}
    return pane_titles_from_payload(payload) if isinstance(payload, dict) else {}


def build_projects(data: dict, pane_titles: dict[str, str] | None = None) -> list[dict]:
    pane_titles = pane_titles or {}
    current_session = os.environ.get("HERDR_SESSION")
    projects: dict[str, dict] = {}
    all_orchs = data.get("orchs", {})
    for key, orch in all_orchs.items():
        project_path = str(orch.get("project", ""))
        project = projects.setdefault(project_path, {"path": project_path, "name": Path(project_path).name or "unknown project", "queue_count": 0, "rows": []})
        project["queue_count"] += len(orch.get("queue", []))
        if not orch.get("gone", False):
            name = orch.get("name") or key.split("/", 1)[-1]
            session = key.rpartition("/")[0]
            title_key = f"{session}/{orch.get('pane')}"
            title = pane_titles.get(title_key, "") if current_session and session == current_session else ""
            project["rows"].append({"node": orch, "kind": "ORCH", "path": [name], "orphan": False, "group": key, "group_name": name, "title": title})

    for key, agent in data.get("agents", {}).items():
        project_path = str(agent.get("project", ""))
        project = projects.setdefault(project_path, {"path": project_path, "name": Path(project_path).name or "unknown project", "queue_count": 0, "rows": []})
        owner_key = agent.get("orch")
        owner = all_orchs.get(owner_key, {})
        is_orphan = not owner or owner.get("gone", False) or owner.get("project") != project_path
        if is_orphan:
            parts = ["ORPHAN", agent.get("name") or key.split("/", 1)[-1]]
            group = "__orphans__"
            group_name = "ORPHANS"
        else:
            parts = [owner.get("name") or owner_key.split("/", 1)[-1], agent.get("name") or key.split("/", 1)[-1]]
            group = owner_key
            group_name = owner.get("name") or owner_key.split("/", 1)[-1]
        session = key.rpartition("/")[0]
        title_key = f"{session}/{agent.get('pane')}"
        title = pane_titles.get(title_key, "") if current_session and session == current_session else ""
        project["rows"].append({"node": agent, "kind": "AGENT", "path": parts, "orphan": is_orphan, "group": group, "group_name": group_name, "title": title})

    result = list(projects.values())
    for project in result:
        project["rows"].sort(key=row_sort_key)
    result.sort(key=lambda item: item["name"].casefold())
    return result


def row_sort_key(row: dict) -> tuple:
    status = str(row["node"].get("status", "unknown")).lower()
    rank = STATUS_ORDER.get(status, 3)
    return row["orphan"], str(row["group_name"]).casefold(), str(row["group"]).casefold(), 0 if row["kind"] == "ORCH" else 1, rank, str(row["path"][-1]).casefold(), row["kind"]


def status_cell(row: dict, enabled: bool) -> str:
    if row["kind"] == "ORCH" and row["node"].get("paused"):
        held = int(row["node"]["paused"].get("count", 0))
        return color(f"PAUSED {held}", "amber", enabled, terminal_color_mode())
    status = str(row["node"].get("status", "unknown")).lower()
    if row["kind"] == "AGENT" and row["node"].get("state") in ("closing", "cleanup", "not-started"):
        status = row["node"]["state"]
    display_status = status if status in STATUS_COLORS else "unknown"
    role = STATUS_COLORS[display_status]
    return color(display_status, role, enabled, terminal_color_mode())


def orch_status_text(row: dict) -> str:
    node = row["node"]
    status = str(node.get("status", "unknown")).lower()
    if status not in STATUS_COLORS:
        status = "unknown"
    queue_count = len(node.get("queue", []))
    if node.get("paused"):
        return f"PAUSED {int(node['paused'].get('count', 0))}  Q:{queue_count}"
    return f"{status}  Q:{queue_count}"


def runtime_label(row: dict) -> str:
    node = row["node"]
    host = str(node.get("kind", node.get("host", "unknown")))
    model = str(node.get("model") or "")
    suffix = f"{host} {model}".strip()
    if row["kind"] == "ORCH":
        suffix += f" · Q:{len(node.get('queue', []))}"
    return suffix


def table_layout(width: int, required_runtime_width: int | None = None, required_path_width: int = MIN_WORKER_PATH_WIDTH) -> tuple[int, int, int]:
    state_limit = 11 if width < 84 else STATE_WIDTH
    state_width = min(state_limit, max(1, width - 4))
    path_reservation = max(MIN_PATH_WIDTH, required_path_width)
    available_runtime = width - state_width - 6 - path_reservation
    runtime_width = min(MAX_RUNTIME_WIDTH, max(MIN_RUNTIME_WIDTH, required_runtime_width or MIN_RUNTIME_WIDTH), available_runtime) if available_runtime >= MIN_RUNTIME_WIDTH else 0
    path_width = max(0, width - state_width - 3 - (3 + runtime_width if runtime_width else 0))
    return state_width, path_width, runtime_width


def middle_truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if display_width(value) <= limit:
        return value
    if limit == 1:
        return "…"
    left_budget = (limit - 1 + 1) // 2
    right_budget = limit - 1 - left_budget
    left = ""
    used = 0
    for char in value:
        char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used + char_width > left_budget:
            break
        left += char
        used += char_width
    right = ""
    used = 0
    for char in reversed(value[len(left):]):
        char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used + char_width > right_budget:
            break
        right = char + right
        used += char_width
    return left + "…" + right


def path_reservation(row: dict) -> int:
    parts = [str(part) for part in row.get("path", [])]
    if len(parts) < 2:
        return MIN_PATH_WIDTH
    owner_width = min(MIN_OWNER_WIDTH, display_width(" > ".join(parts[:-1])))
    worker_width = min(MIN_WORKER_WIDTH, display_width(parts[-1]))
    return max(MIN_PATH_WIDTH, owner_width + display_width(" > ") + worker_width)


def fit_path(parts: list[str], width: int) -> str:
    if not parts:
        return truncate("", width)
    if len(parts) == 1:
        return truncate(parts[0], width)
    separator = " > "
    if sum(display_width(part) for part in parts) + display_width(separator) * (len(parts) - 1) <= width:
        return separator.join(parts)
    owner = " > ".join(parts[:-1])
    owner_width = min(MIN_OWNER_WIDTH, display_width(owner))
    separator_width = display_width(separator)
    if width < owner_width + separator_width + 1:
        return truncate(separator.join(parts), width)
    worker_width = width - owner_width - separator_width
    return f"{truncate(owner, owner_width)}{separator}{middle_truncate(parts[-1], worker_width)}"


def row_line(row: dict, width: int, enabled: bool, with_runtime: bool, runtime_width: int = 0, required_path_width: int = MIN_WORKER_PATH_WIDTH) -> str:
    state_width, path_width, runtime_width = table_layout(width, runtime_width, required_path_width)
    path = fit_path([str(part) for part in row["path"]], path_width)
    if row["orphan"]:
        path = path.replace("ORPHAN", color("ORPHAN", "1;35", enabled), 1)
    state = status_cell(row, enabled)
    state = truncate(state, state_width)
    line = f"{state}{' ' * max(0, state_width - display_width(state))} | {path}{' ' * max(0, path_width - display_width(path))}"
    if with_runtime:
        line += f" | {truncate(runtime_label(row), runtime_width)}"
    return truncate(line, width)


def footer(registry: str, refreshed_at: str, width: int) -> str:
    return padded_line("q quit", width)


def padded_line(value: str, width: int) -> str:
    inner = max(0, width - 4)
    value = truncate(value, inner)
    return f"  {value}{' ' * max(0, inner - display_width(value))}  "


def count_label(count: int, singular: str, plural: str) -> str:
    noun = singular
    if count != 1:
        noun = plural
    return f"{count} {noun}"


def visible_rows(projects: list[dict], now: float) -> list[dict]:
    rows = [row for project in projects for row in project["rows"]]
    def retained(row: dict) -> bool:
        if row["kind"] != "AGENT":
            return True
        node = row["node"]
        closing = node.get("state") in ("cleanup", "closed") or str(node.get("status", "unknown")).lower() == "closed"
        if not closing:
            return True
        closed_at = node.get("closed_at")
        return closed_at is not None and now - closed_at <= CLOSED_ROW_SECONDS
    return [row for row in rows if retained(row)]


def agent_lines(row: dict, width: int, enabled: bool, last: bool, status_width: int | None = None) -> list[str]:
    name = str(row["node"].get("name") or row["path"][-1])
    connector = "└ " if last else "├ "
    if row.get("orphan"):
        connector = "* "
    return [format_row(connector + name, status_cell(row, enabled), "", row.get("title", ""), width, status_width)]


def column_widths(width: int, required_status_width: int = 12) -> tuple[int, int, int, int]:
    available = max(1, width - 4 - 6)
    status = min(max(12, required_status_width), max(1, available - 3))
    if available < 50:
        remaining = max(3, available - status)
        name = min(13, max(1, remaining // 3 + 2))
        project = min(10, max(1, remaining // 3))
    else:
        name = min(30, max(22, available // 3))
        project = 16
    title = max(1, available - name - status - project)
    return name, status, project, title


def format_row(name: str, status: str, project: str, title: str, width: int, status_width: int | None = None) -> str:
    widths = column_widths(width, status_width or 12)
    values = (name, status, project, title)
    cells = [truncate(value, limit) for value, limit in zip(values, widths)]
    plain = "  ".join(f"{value}{' ' * max(0, limit - display_width(value))}" for value, limit in zip(cells, widths))
    return padded_line(plain, width)


def orch_section(row: dict, agents: list[dict], project_name: str, multiple_projects: bool, width: int, enabled: bool, status_width: int | None = None) -> list[str]:
    node = row["node"]
    name = str(node.get("name") or row["group_name"])
    status = status_cell(row, enabled)
    queue = len(node.get("queue", []))
    if node.get("paused"):
        status = color(f"PAUSED {int(node['paused'].get('count', 0))}", "amber", enabled, terminal_color_mode())
    else:
        status += color(f"  Q:{queue}", "amber", enabled, terminal_color_mode())
    if node.get("paused"):
        status += color(f"  Q:{queue}", "amber", enabled, terminal_color_mode())
    lines = [format_row("▾ " + name, status, project_name, row.get("title", ""), width, status_width)]
    for index, agent in enumerate(agents):
        lines.extend(agent_lines(agent, width, enabled, index == len(agents) - 1, status_width))
    return lines


def render(data: dict, width: int, enabled: bool, registry: str, refreshed_at: str, error: str | None = None, now: float | None = None, pane_titles: dict[str, str] | None = None) -> str:
    if now is None:
        now = time.time()
    projects = build_projects(data, pane_titles)
    rows = visible_rows(projects, now)
    orch_rows = [row for row in rows if row["kind"] == "ORCH"]
    agent_rows = [row for row in rows if row["kind"] == "AGENT"]
    orch_count = len(orch_rows)
    agent_count = sum(str(row["node"].get("status", "unknown")).lower() != "closed" for row in agent_rows)
    status_width = max((display_width(orch_status_text(row)) for row in orch_rows), default=12)
    stamp = re.search(r"\d{2}:\d{2}:\d{2}", refreshed_at)
    last = stamp.group(0) if stamp else refreshed_at[-8:]
    lines = [
        padded_line(color(f"orch board v{BOARD_VERSION}", "header", enabled, terminal_color_mode()), width),
        padded_line(f"refresh: {REFRESH_SECONDS}s · last: {last}", width),
        padded_line(f"Status: All · {count_label(orch_count, 'orch', 'orchs')} · {count_label(agent_count, 'agent', 'agents')}", width),
        "",
        format_row("Name", "Status", "Project", "Title", width, status_width),
        padded_line("─" * max(1, width - 4), width),
        "",
    ]
    if error:
        lines.append(padded_line(color(f"Registry read failed: {error}", "blocked", enabled, terminal_color_mode()), width))
    elif not projects:
        lines.append(padded_line("No projects or agents registered.", width))
    else:
        for project in projects:
            queue_label = f" · {project['queue_count']} queued" if project["queue_count"] else ""
            heading = color(f"{project['name']}{queue_label}", "app", enabled, terminal_color_mode())
            lines.append(padded_line(heading, width))
            rows = visible_rows([project], now)
            orchs = [row for row in rows if row["kind"] == "ORCH"]
            agents = [row for row in rows if row["kind"] == "AGENT"]
            if not orchs and not agents:
                lines.append(padded_line("No live orchs or agents.", width))
            for orch in sorted(orchs, key=row_sort_key):
                children = sorted((agent for agent in agents if agent["group"] == orch["group"] and not agent["orphan"]), key=row_sort_key)
                lines.extend(orch_section(orch, children, project["name"], False, width, enabled, status_width))
            orphans = sorted((row for row in agents if row["orphan"]), key=row_sort_key)
            if orphans:
                lines.append(padded_line(color("orphans", "orphan", enabled, terminal_color_mode()), width))
                for index, row in enumerate(orphans):
                    lines.extend(agent_lines(row, width, enabled, index == len(orphans) - 1, status_width))
            if project is not projects[-1]:
                lines.append("")
    lines.append("")
    lines.append(footer(registry, refreshed_at, width))
    return "\n".join(lines)


def write_frame(output: str, clear: bool = False) -> None:
    prefix = "\033[H\033[2J" if clear else "\033[H"
    lines = output.split("\n")
    sys.stdout.write(prefix + "\n".join(line + "\033[K" for line in lines) + "\n\033[J")


class Board:
    def __init__(self, path: Path, width: int, color_enabled: bool, clock=None):
        self.path = Path(path)
        self.width = width
        self.color_enabled = color_enabled
        self.clock = clock or (lambda: datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
        self.mtime_ns = None
        self.loaded = False
        self.refreshed_at = "never"
        self.output = ""
        self.data = {"version": 1, "orchs": {}, "agents": {}}
        self.error = None
        self.now = time.time
        self.titles = {}

    def set_width(self, width: int) -> bool:
        if width == self.width:
            return False
        self.width = width
        if self.loaded:
            self.output = render(self.data, self.width, self.color_enabled, str(self.path), self.refreshed_at, self.error, pane_titles=self.titles)
        return True

    def refresh(self) -> bool:
        self.titles = read_pane_titles() if os.environ.get("HERDR_ENV") else {}
        self.refreshed_at = self.clock()
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        if self.loaded and mtime_ns == self.mtime_ns:
            output = render(self.data, self.width, self.color_enabled, str(self.path), self.refreshed_at, self.error, now=self.now(), pane_titles=self.titles)
            changed = output != self.output
            self.output = output
            return changed
        data = {"version": 1, "orchs": {}, "agents": {}}
        error = None
        if mtime_ns is not None:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                error = str(exc)
        self.mtime_ns = mtime_ns
        self.loaded = True
        self.data = data
        self.error = error
        self.output = render(data, self.width, self.color_enabled, str(self.path), self.refreshed_at, error, now=self.now(), pane_titles=self.titles)
        return True


def run(board: Board, dynamic_width: bool = True) -> None:
    import termios
    import tty

    old_settings = None
    if sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    try:
        write_frame(board.output, clear=True)
        sys.stdout.flush()
        while True:
            previous = board.output
            changed = board.refresh()
            if dynamic_width:
                changed = board.set_width(shutil.get_terminal_size((100, 24)).columns) or changed
            if changed:
                old_lines = previous.splitlines()
                new_lines = board.output.splitlines()
                changed_lines = [index for index, (old, new) in enumerate(zip(old_lines, new_lines)) if old != new]
                if len(old_lines) == len(new_lines) and changed_lines == [1]:
                    sys.stdout.write(f"\033[s\033[{changed_lines[0] + 1};1H" + new_lines[1] + "\033[K\033[u")
                else:
                    write_frame(board.output)
                sys.stdout.flush()
            fd = sys.stdin.fileno()
            readable, _, _ = select.select([fd], [], [], 1.0)
            if readable:
                keys = os.read(fd, 4096).decode(errors="ignore")
                if "q" in keys.lower() or not keys:
                    break
        sys.stdout.write(f"\033[{len(board.output.splitlines()) + 1};1H")
        sys.stdout.flush()
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)


def open_board(placement: str = "split") -> None:
    pane = os.environ.get("HERDR_PANE_ID")
    if not os.environ.get("HERDR_ENV") or not pane:
        raise SystemExit("orch board: --open must run inside a Herdr pane")
    if placement not in ("split", "overlay"):
        raise SystemExit("orch board: placement must be 'split' or 'overlay'")
    command = ["herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board", "--placement", placement]
    if placement == "split":
        direction = os.environ.get("ORCH_BOARD_DIRECTION", "right")
        if direction not in ("right", "down"):
            raise SystemExit("orch board: ORCH_BOARD_DIRECTION must be 'right' or 'down'")
        command.extend(["--target-pane", pane, "--direction", direction])
    try:
        opened = subprocess.run(command, text=True, capture_output=True)
    except FileNotFoundError as exc:
        print(f"orch board: could not launch herdr: {exc}", file=sys.stderr)
        print(" ".join(command))
        raise SystemExit(127)
    if opened.returncode:
        diagnostic = (opened.stderr or opened.stdout).strip()
        if diagnostic:
            print(f"orch board: failed to open board pane: {diagnostic}", file=sys.stderr)
        print(" ".join(command))
        raise SystemExit(opened.returncode)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="render once and exit")
    parser.add_argument("--open", action="store_true", help="open the board as a Herdr plugin pane")
    parser.add_argument("--placement", choices=("split", "overlay"), default="split", help="placement for --open")
    parser.add_argument("--width", type=int, help="override the pane width")
    parser.add_argument("--registry", type=Path, help="registry path (defaults to the orch state registry)")
    args = parser.parse_args(argv)
    dynamic_width = args.width is None
    width = args.width if args.width is not None else shutil.get_terminal_size((100, 24)).columns
    if width < 1:
        parser.error("--width must be a positive number of columns")
    if args.open:
        open_board(args.placement)
        return
    path = args.registry or registry_path()
    enabled = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    view = Board(path, width, enabled)
    view.refresh()
    if args.once:
        print(view.output)
    else:
        run(view, dynamic_width=dynamic_width)


if __name__ == "__main__":
    main()
