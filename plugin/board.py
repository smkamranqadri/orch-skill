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
import unicodedata
from datetime import datetime
from pathlib import Path


ANSI_RE = re.compile(r"\033\[[0-9;]*m")
STATUS_ORDER = {"blocked": 0, "working": 2, "idle": 3, "done": 3, "unknown": 3}
STATUS_COLORS = {"blocked": "1;31", "working": "32", "idle": "36", "done": "32", "unknown": "33"}


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
            project["rows"].append({"node": orch, "kind": "ORCH", "path": [orch.get("name") or key.split("/", 1)[-1]], "orphan": False})

    for key, agent in data.get("agents", {}).items():
        project_path = str(agent.get("project", ""))
        project = projects.setdefault(project_path, {"path": project_path, "name": Path(project_path).name or "unknown project", "queue_count": 0, "rows": []})
        owner_key = agent.get("orch")
        owner = all_orchs.get(owner_key, {})
        is_orphan = not owner or owner.get("gone", False) or owner.get("project") != project_path
        if is_orphan:
            parts = ["ORPHAN", agent.get("name") or key.split("/", 1)[-1]]
        else:
            parts = [owner.get("name") or owner_key.split("/", 1)[-1], agent.get("name") or key.split("/", 1)[-1]]
        project["rows"].append({"node": agent, "kind": "AGENT", "path": parts, "orphan": is_orphan})

    result = list(projects.values())
    for project in result:
        project["rows"].sort(key=row_sort_key)
    result.sort(key=lambda item: item["name"].casefold())
    return result


def row_sort_key(row: dict) -> tuple:
    status = str(row["node"].get("status", "unknown")).lower()
    rank = STATUS_ORDER.get(status, 3)
    if row["orphan"]:
        rank = 1
    return rank, str(row["path"][-1]).casefold(), row["kind"]


def status_cell(row: dict, enabled: bool) -> str:
    status = str(row["node"].get("status", "unknown")).lower()
    label = status.upper()
    if row["orphan"]:
        label += " *"
        return color(label, "1;35", enabled)
    if status == "blocked":
        label += " !"
    return color(label, STATUS_COLORS.get(status, STATUS_COLORS["unknown"]), enabled)


def row_line(row: dict, width: int, enabled: bool, with_runtime: bool) -> str:
    state_width = 18
    runtime_width = min(26, max(18, width // 4)) if with_runtime else 0
    separators = 3 + (3 + runtime_width if with_runtime else 0)
    path_width = max(1, width - state_width - separators)
    parts = row["path"]
    path = " / ".join(str(part) for part in parts)
    if row["orphan"]:
        path = path.replace("ORPHAN", color("ORPHAN", "1;35", enabled), 1)
    state = status_cell(row, enabled)
    state_plain_width = display_width(state)
    line = f"{state}{' ' * max(1, state_width - state_plain_width)} | {truncate(path, path_width)}"
    if with_runtime:
        node = row["node"]
        host = str(node.get("kind", node.get("host", "unknown")))
        model = str(node.get("model", ""))
        suffix = f"{host} {model}".strip()
        if row["kind"] == "ORCH":
            suffix += f" · Q:{len(node.get('queue', []))}"
        line += f" | {truncate(suffix, runtime_width)}"
    return line


def footer(registry: str, refreshed_at: str, width: int) -> str:
    ending = f" · refreshed {refreshed_at}"
    prefix = "Registry: "
    path_limit = max(1, width - display_width(prefix + ending))
    if display_width(registry) > path_limit and path_limit > 1:
        tail = ""
        used = 0
        for char in reversed(registry):
            char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
            if used + char_width > path_limit - 1:
                break
            tail = char + tail
            used += char_width
        registry = "…" + tail
    else:
        registry = truncate(registry, path_limit)
    return prefix + registry + ending


def render(data: dict, width: int, enabled: bool, registry: str, refreshed_at: str, error: str | None = None) -> str:
    projects = build_projects(data)
    orch_count = sum(row["kind"] == "ORCH" for project in projects for row in project["rows"])
    agent_count = sum(row["kind"] == "AGENT" for project in projects for row in project["rows"])
    lines = [
        truncate(color(f"ORCH BOARD · {len(projects)} projects · {orch_count} orchs · {agent_count} agents", "1;37", enabled), width),
        truncate("Legend: ! blocked; * orphan; working; idle; done; unknown", width),
        "-" * width,
    ]
    if error:
        lines.append(truncate(color(f"Registry read failed: {error}", "1;31", enabled), width))
    elif not projects:
        lines.append(truncate("No projects or agents registered.", width))
    else:
        with_runtime = width >= 84
        if with_runtime:
            lines.append(truncate(f"{'STATE':<18} | {'HIERARCHY PATH':<{width - 18 - 32}} | HOST / MODEL", width))
        else:
            lines.append(truncate(f"{'STATE':<18} | HIERARCHY PATH", width))
        for project in projects:
            lines.append(truncate(color(f"{project['name']} · {project['queue_count']} queued notices", "1;36", enabled), width))
            if not project["rows"]:
                lines.append(truncate("  No orchs or agents.", width))
            else:
                lines.extend(row_line(row, width, enabled, with_runtime) for row in project["rows"])
            lines.append("")
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

    def refresh(self) -> bool:
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        if self.loaded and mtime_ns == self.mtime_ns:
            return False
        data = {"version": 1, "orchs": {}, "agents": {}}
        error = None
        if mtime_ns is not None:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                error = str(exc)
        self.mtime_ns = mtime_ns
        self.loaded = True
        self.refreshed_at = self.clock()
        self.output = render(data, self.width, self.color_enabled, str(self.path), self.refreshed_at, error)
        return True


def run(board: Board) -> None:
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
            if changed:
                sys.stdout.write("\033[H\033[2J" + board.output + "\n")
                sys.stdout.flush()
            readable, _, _ = select.select([sys.stdin], [], [], 1.0)
            if readable:
                key = sys.stdin.read(1)
                if key.lower() == "q" or key == "":
                    break
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)


def open_board() -> None:
    pane = os.environ.get("HERDR_PANE_ID")
    if not os.environ.get("HERDR_ENV") or not pane:
        raise SystemExit("orch board: --open must run inside a Herdr pane")
    project = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if project.returncode:
        raise SystemExit("orch board: current directory is not in a git repository")
    opened = subprocess.run([
        "herdr", "plugin", "pane", "open", "--plugin", "orch", "--entrypoint", "board",
        "--placement", "split", "--target-pane", pane, "--direction", "right", "--cwd", project.stdout.strip(),
    ], text=True, capture_output=True)
    if opened.returncode:
        raise SystemExit(f"orch board: failed to open board pane: {(opened.stderr or opened.stdout).strip()}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="render once and exit")
    parser.add_argument("--open", action="store_true", help="open the board as a Herdr plugin pane")
    parser.add_argument("--width", type=int, help="override the pane width")
    parser.add_argument("--registry", type=Path, help="registry path (defaults to the orch state registry)")
    args = parser.parse_args(argv)
    width = args.width or shutil.get_terminal_size((100, 24)).columns
    if width < 40:
        parser.error("--width must be at least 40 columns")
    if args.open:
        open_board()
        return
    path = args.registry or registry_path()
    enabled = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    view = Board(path, width, enabled)
    view.refresh()
    if args.once:
        print(view.output)
    else:
        run(view)


if __name__ == "__main__":
    main()
