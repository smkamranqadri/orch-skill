#!/usr/bin/env bash
# Compact live Herdr state for the orchestrator: only the fields it needs.
#
#   orch-agents.sh [--fields a,b,...] [<name-or-pane>]           live agents
#   orch-agents.sh --panes [--fields a,b,...] [<name-or-pane>]   live panes
#
# Prints a header row and one row per entry, sorted by the first field. It never prints the
# full `herdr agent list` / `herdr pane list` JSON (about 12.6k chars per call): the
# orchestrator reads this instead. Agent fields: name,pane,status,model,cwd. Pane fields:
# pane,label,cwd,agent. Exit 0 on success, 2 when a given target is not live, 3 when the live
# list cannot be read, 64 on usage errors. Tests set ORCH_AGENTS_FIXTURE_LIST /
# ORCH_AGENTS_FIXTURE_PANES (JSON files), the same way orch-model.sh uses
# ORCH_MODEL_FIXTURE_LIST.
set -uo pipefail

usage() { echo "usage: orch-agents.sh [--panes] [--fields a,b,...] [<name-or-pane>]" >&2; }

kind="agents"; fields=""; target=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --panes) kind="panes"; shift ;;
    --fields) [[ $# -ge 2 ]] || { usage; exit 64; }; fields="$2"; shift 2 ;;
    --fields=*) fields="${1#--fields=}"; shift ;;
    -h|--help) cat <<'USAGE'
usage: orch-agents.sh [--panes] [--fields a,b,...] [<name-or-pane>]

  agents (default)  fields: name,pane,status,model,cwd
  --panes           fields: pane,label,cwd,agent
  --fields a,b,...  any subset of that source's fields, in this order
  <name-or-pane>    one entry; exit 2 when it is not live
USAGE
      exit 0 ;;
    -*) echo "unknown option: $1" >&2; usage; exit 64 ;;
    *) [[ -z "$target" ]] || { usage; exit 64; }; target="$1"; shift ;;
  esac
done

if [[ "$kind" == "panes" ]]; then
  default_fields="pane,label,cwd,agent"; allowed="pane label cwd agent"
  list_json() {
    if [[ -n "${ORCH_AGENTS_FIXTURE_PANES:-}" ]]; then cat "$ORCH_AGENTS_FIXTURE_PANES"; else herdr pane list 2>/dev/null; fi
  }
else
  default_fields="name,pane,status,model,cwd"; allowed="name pane status model cwd"
  list_json() {
    if [[ -n "${ORCH_AGENTS_FIXTURE_LIST:-}" ]]; then cat "$ORCH_AGENTS_FIXTURE_LIST"; else herdr agent list 2>/dev/null; fi
  }
fi
[[ -n "$fields" ]] || fields="$default_fields"

IFS=',' read -r -a want <<< "$fields"
for f in "${want[@]}"; do
  [[ -n "$f" ]] || continue
  [[ " $allowed " == *" $f "* ]] || { echo "unknown field: $f (allowed: $allowed)" >&2; exit 64; }
done

list_json | python3 -I -c '
import json, sys

fields = [f for f in sys.argv[1].split(",") if f]
target = sys.argv[2]
kind = sys.argv[3]
key = "agents" if kind == "agents" else "panes"
label = "agent list" if kind == "agents" else "pane list"

try:
    items = json.load(sys.stdin)["result"][key]
except Exception:
    print("orch-agents: live %s unavailable" % label, file=sys.stderr)
    sys.exit(3)

def value(item, name):
    if name == "name":
        return item.get("name")
    if name == "pane":
        return item.get("pane_id")
    if name == "status":
        return item.get("agent_status")
    if name == "model":
        return (item.get("tokens") or {}).get("model")
    if name == "cwd":
        return item.get("cwd") or item.get("foreground_cwd")
    if name == "label":
        return item.get("label") or item.get("title")
    if name == "agent":
        return item.get("agent")
    return None

if target:
    if kind == "agents":
        items = [i for i in items if target in (i.get("name"), i.get("pane_id"))]
    else:
        items = [i for i in items if target in (i.get("pane_id"), i.get("label"))]
    if not items:
        print("no live %s for %s" % ("agent" if kind == "agents" else "pane", target), file=sys.stderr)
        sys.exit(2)

rows = [["-" if value(i, f) in (None, "") else str(value(i, f)) for f in fields] for i in items]
rows.sort(key=lambda r: (r[0] == "-", r[0]))

widths = [max([len(fields[c])] + [len(r[c]) for r in rows]) for c in range(len(fields))]
def line(vals):
    return "  ".join(v.ljust(widths[c]) for c, v in enumerate(vals)).rstrip()
print(line(fields))
for r in rows:
    print(line(r))
' "$fields" "$target" "$kind"
