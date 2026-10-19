#!/usr/bin/env python3
"""Resolve the plugin directory from `herdr plugin list --json`."""
import json
import sys
import tomllib
from pathlib import Path


def entries(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("plugins", "result", "items"):
            nested = value.get(key)
            if isinstance(nested, (list, dict)):
                return entries(nested)
        return [value]
    return []


def plugin_directory(item):
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    for key in ("path", "plugin_path", "directory", "dir", "root", "source", "install_path"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def is_orch_plugin(root):
    manifest = root / "herdr-plugin.toml"
    executable = root / "orch"
    if not manifest.is_file() or not executable.is_file():
        return False
    try:
        with manifest.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return data.get("id") == "orch"


try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError) as exc:
    print(f"invalid Herdr plugin list JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)

for entry in entries(data):
    if isinstance(entry, dict):
        identity = entry.get("id") or entry.get("name") or entry.get("plugin")
        if identity and str(identity).split("/")[-1] != "orch":
            continue
    candidate = plugin_directory(entry)
    if not candidate:
        continue
    root = Path(candidate).expanduser()
    if root.is_file():
        root = root.parent
    if root.name == "plugin" and (root / "herdr-plugin.toml").is_file():
        pass
    elif (root / "plugin" / "herdr-plugin.toml").is_file():
        root = root / "plugin"
    if is_orch_plugin(root):
        print(root.resolve())
        raise SystemExit(0)

print("Herdr plugin list did not include an orch plugin directory", file=sys.stderr)
raise SystemExit(1)
