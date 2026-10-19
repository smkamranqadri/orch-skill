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
STATUS_ORDER = {"blocked": 0, "working": 2, "idle": 3, "done": 3, "unknown": 3, "closed": 4}
STATUS_GLYPHS = {"blocked": "!", "working": "▶", "idle": "○", "done": "✓", "unknown": "?", "closed": "×"}
STATUS_COLORS = {"blocked": "1;31", "working": "1;34", "idle": "36", "done": "32", "unknown": "33", "closed": "2;37"}
STATE_WIDTH = 18
MIN_PATH_WIDTH = 14
MIN_OWNER_WIDTH = 6
MIN_WORKER_WIDTH = 20
MIN_WORKER_PATH_WIDTH = MIN_OWNER_WIDTH + 3 + MIN_WORKER_WIDTH
MIN_RUNTIME_WIDTH = len("HOST / MODEL")
MAX_RUNTIME_WIDTH = 26
CLOSED_ROW_SECONDS = 600


def color(value: str, code: str, enabled: bool) -> str:
    if not enabled:
        return value
    return f"\033[{code}m{value}\033[0m"


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


def build_projects(data: dict) -> list[dict]:
    projects: dict[str, dict] = {}
    all_orchs = data.get("orchs", {})
    for key, orch in all_orchs.items():
        project_path = str(orch.get("project", ""))
        project = projects.setdefault(project_path, {"path": project_path, "name": Path(project_path).name or "unknown project", "queue_count": 0, "rows": []})
        project["queue_count"] += len(orch.get("queue", []))
        if not orch.get("gone", False):
            name = orch.get("name") or key.split("/", 1)[-1]
            project["rows"].append({"node": orch, "kind": "ORCH", "path": [name], "orphan": False, "group": key, "group_name": name})

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
        project["rows"].append({"node": agent, "kind": "AGENT", "path": parts, "orphan": is_orphan, "group": group, "group_name": group_name})

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
        return color(f"PAUSED {held}", "1;33", enabled)
    status = str(row["node"].get("status", "unknown")).lower()
    display_status = status if status in STATUS_GLYPHS else "unknown"
    glyph = STATUS_GLYPHS[display_status]
    label = f"{glyph} {display_status.upper()}"
    if status == "closed":
        if row["orphan"]:
            label += " *"
        return color(label, STATUS_COLORS["closed"], enabled)
    if row["orphan"]:
        label += " *"
        return color(label, "1;35", enabled)
    return color(label, STATUS_COLORS.get(status, STATUS_COLORS["unknown"]), enabled)


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
    clock = re.search(r"\d{2}:\d{2}:\d{2}", refreshed_at)
    short_time = clock.group(0) if clock else refreshed_at[-8:]
    return truncate(f"refreshed {short_time}", width)


def count_label(count: int, singular: str, plural: str) -> str:
    noun = singular
    if count != 1:
        noun = plural
    return f"{count} {noun}"


def visible_rows(projects: list[dict], now: float) -> list[dict]:
    rows = [row for project in projects for row in project["rows"]]
    return [
        row for row in rows
        if row["kind"] != "AGENT"
        or str(row["node"].get("status", "unknown")).lower() != "closed"
        or (row["node"].get("closed_at") is not None and now - row["node"]["closed_at"] <= CLOSED_ROW_SECONDS)
    ]


def agent_lines(row: dict, width: int, enabled: bool, last: bool) -> list[str]:
    state_width = 11 if width < 84 else STATE_WIDTH
    state = truncate(status_cell(row, enabled), state_width)
    connector = "└─" if last else "├─"
    name = str(row["node"].get("name") or row["path"][-1])
    prefix = f"{state}{' ' * max(0, state_width - display_width(state))} |   {connector} "
    continuation = " " * display_width(prefix)
    available = max(1, width - display_width(prefix))
    chunks = []
    current = ""
    for char in name:
        if current and display_width(current + char) > available:
            chunks.append(current)
            current = ""
        current += char
    if current or not chunks:
        chunks.append(current)
    return [truncate((prefix if index == 0 else continuation) + chunk, width) for index, chunk in enumerate(chunks)]


def orch_section(row: dict, agents: list[dict], project_name: str, multiple_projects: bool, width: int, enabled: bool) -> list[str]:
    node = row["node"]
    status = status_cell(row, enabled)
    name = str(node.get("name") or row["group_name"])
    if multiple_projects:
        name = f"{name} · {project_name}"
    runtime = runtime_label(row)
    state_width = 11 if width < 84 else STATE_WIDTH
    suffix = f" | {runtime}"
    name_width = max(0, width - state_width - 3 - display_width(suffix))
    section_name = truncate(name, name_width)
    heading = f"{status}{' ' * max(0, state_width - display_width(status))} | {section_name}{suffix}"
    lines = [truncate(heading, width)]
    for index, agent in enumerate(agents):
        lines.extend(agent_lines(agent, width, enabled, index == len(agents) - 1))
    return lines


def render(data: dict, width: int, enabled: bool, registry: str, refreshed_at: str, error: str | None = None, now: float | None = None) -> str:
    if now is None:
        now = time.time()
    projects = build_projects(data)
    rows = visible_rows(projects, now)
    orch_rows = [row for row in rows if row["kind"] == "ORCH"]
    agent_rows = [row for row in rows if row["kind"] == "AGENT"]
    orch_count = len(orch_rows)
    agent_count = sum(str(row["node"].get("status", "unknown")).lower() != "closed" for row in agent_rows)
    project_names = {project["path"]: project["name"] for project in projects}
    multiple_projects = len(projects) > 1
    heading = f"ORCH BOARD · {count_label(len(projects), 'project', 'projects')} · {count_label(orch_count, 'orch', 'orchs')} · {count_label(agent_count, 'agent', 'agents')}"
    if display_width(heading) > width:
        heading = f"ORCH · {len(projects)}P · {orch_count}O · {agent_count}A"
    lines = [
        truncate(color(heading, "1;37", enabled), width),
        "-" * width,
    ]
    if error:
        lines.append(truncate(color(f"Registry read failed: {error}", "1;31", enabled), width))
    elif not projects:
        lines.append(truncate("No projects or agents registered.", width))
    elif not orch_rows and not agent_rows:
        lines.append(truncate("No live orchs or agents.", width))
    else:
        sections = []
        for orch in orch_rows:
            project_name = project_names.get(str(orch["node"].get("project", "")), "unknown project")
            agents = sorted((agent for agent in agent_rows if agent["group"] == orch["group"] and not agent["orphan"]), key=row_sort_key)
            sections.append((project_name.casefold(), str(orch["node"].get("name") or orch["group_name"]).casefold(), orch, agents, project_name))
        sections.sort(key=lambda section: (section[0], section[1]))
        for _, _, orch, agents, project_name in sections:
            lines.extend(orch_section(orch, agents, project_name, multiple_projects, width, enabled))
            lines.append("")
        orphan_rows = sorted((row for row in agent_rows if row["orphan"]), key=lambda row: (project_names.get(str(row["node"].get("project", "")), "unknown project").casefold(), *row_sort_key(row)))
        if orphan_rows:
            lines.append("ORPHANS")
            for index, row in enumerate(orphan_rows):
                lines.extend(agent_lines(row, width, enabled, index == len(orphan_rows) - 1))
        elif not sections:
            lines.append(truncate("No live orchs or agents.", width))
    for project in projects:
        if project["queue_count"]:
            label = count_label(project["queue_count"], "queued notice", "queued notices")
            lines.append(truncate(color(f"{project['name']} · {label}", "1;36", enabled), width))
    while lines and lines[-1] == "":
        lines.pop()
    lines.append(footer(registry, refreshed_at, width))
    return "\n".join(lines)


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

    def set_width(self, width: int) -> bool:
        if width == self.width:
            return False
        self.width = width
        if self.loaded:
            self.output = render(self.data, self.width, self.color_enabled, str(self.path), self.refreshed_at, self.error)
        return True

    def refresh(self) -> bool:
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        if self.loaded and mtime_ns == self.mtime_ns:
            output = render(self.data, self.width, self.color_enabled, str(self.path), self.refreshed_at, self.error, now=self.now())
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
        self.refreshed_at = self.clock()
        self.output = render(data, self.width, self.color_enabled, str(self.path), self.refreshed_at, error, now=self.now())
        return True


def run(board: Board, dynamic_width: bool = True) -> None:
    import termios
    import tty

    old_settings = None
    if sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
    try:
        sys.stdout.write("\033[H\033[2J" + board.output + "\n")
        sys.stdout.flush()
        while True:
            changed = board.refresh()
            if dynamic_width:
                changed = board.set_width(shutil.get_terminal_size((100, 24)).columns) or changed
            if changed:
                sys.stdout.write("\033[H\033[2J" + board.output + "\n")
                sys.stdout.flush()
            fd = sys.stdin.fileno()
            readable, _, _ = select.select([fd], [], [], 1.0)
            if readable:
                keys = os.read(fd, 4096).decode(errors="ignore")
                if "q" in keys.lower() or not keys:
                    break
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
    opened = subprocess.run(command, text=True, capture_output=True)
    if opened.returncode:
        raise SystemExit(f"orch board: failed to open board pane: {(opened.stderr or opened.stdout).strip()}")


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
