#!/usr/bin/env bash
# What kind and model a live Herdr agent is really running, and whether it is the one asked for.
#
#   orch-model.sh <agent-name-or-pane-id>            -> prints "kind=<kind> model=<model>"
#   orch-model.sh <agent-name-or-pane-id> <expected>  -> same, then exit 0 when <expected> is
#                                                        matches the live model (case-insensitive),
#                                                        1 on a mismatch, 2 when no model is visible
#
# Sources, in order: `herdr agent list` (Command Code reports tokens.model there; Claude Code and
# Codex report nothing), then the pane's visible text (Claude Code shows "Opus 5.5", "Sonnet 5.5",
# "Haiku 5.5", "Fable 5.1"; Codex shows "GPT-6.1-Sol medium"). Run it after `herdr agent start`
# and before the first prompt: a wrong model is cheapest to fix before the agent has read anything.
# Tests set ORCH_MODEL_FIXTURE_LIST (agent list JSON file) and ORCH_MODEL_FIXTURE_PANE (pane text).
# Command Code full identifiers compare without provider/ or -(latest); family shorthand,
# and Claude/Codex expectations, retain substring matching.
set -uo pipefail

target="${1:-}"; expected="${2:-}"
[[ -n "$target" ]] || { echo "usage: orch-model.sh <agent|pane> [expected-model]" >&2; exit 64; }

list_json() {
  if [[ -n "${ORCH_MODEL_FIXTURE_LIST:-}" ]]; then cat "$ORCH_MODEL_FIXTURE_LIST"; else herdr agent list 2>/dev/null; fi
}
pane_text() {
  if [[ -n "${ORCH_MODEL_FIXTURE_PANE:-}" ]]; then cat "$ORCH_MODEL_FIXTURE_PANE"; else herdr agent read "$1" --source visible 2>/dev/null; fi
}

read -r kind model pane < <(list_json | python3 -I -c '
import json, sys
t = sys.argv[1]
try:
    agents = json.load(sys.stdin)["result"]["agents"]
except Exception:
    print("- - -"); sys.exit(0)
for a in agents:
    if a.get("name") == t or a.get("pane_id") == t:
        m = (a.get("tokens") or {}).get("model") or "-"
        print(a.get("agent") or "-", m, a.get("pane_id") or "-"); break
else:
    print("- - -")
' "$target")

if [[ "$kind" == "-" ]]; then
  echo "kind=- model=-"; echo "no live agent named $target" >&2; exit 2
fi

if [[ "$model" == "-" ]]; then
  text="$(pane_text "$target" | sed 's/\x1b\[[0-9;?]*[A-Za-z]//g')"
  case "$kind" in
    claude)
      model="$(printf '%s\n' "$text" | grep -oiE '\b(Opus|Sonnet|Haiku|Fable|Mythos)\b( [0-9][0-9.]*)?' | tail -1)" ;;
    codex)
      model="$(printf '%s\n' "$text" | grep -oiE '\bgpt-[0-9][0-9a-z.-]*( (low|medium|high|xhigh|minimal))?' | tail -1)" ;;
    cmd)
      model="$(printf '%s\n' "$text" | grep -oiE '\b(gemini|gpt|claude|opus|sonnet|haiku|deepseek|kimi|glm|minimax|mimo|qwen)[-a-z0-9./]*([(]latest[)])?' | tail -1)" ;;
    *)
      model="$(printf '%s\n' "$text" | grep -oiE '\b(gemini|gpt|claude|opus|sonnet|haiku|deepseek|kimi|glm|minimax|mimo|qwen)[-a-z0-9./ ]*' | tail -1)" ;;
  esac
  model="${model:--}"
fi

echo "kind=$kind model=$model"
[[ -n "$expected" ]] || exit 0
if [[ "$model" == "-" ]]; then
  echo "model not visible for $target ($kind, pane $pane); read the pane yourself before prompting" >&2; exit 2
fi
shopt -s nocasematch
if [[ "$kind" == "cmd" ]]; then
  # Command Code omits the provider in a fresh pane and may label the model -(latest).
  actual_id="${model##*/}"; actual_id="${actual_id%-(latest)}"
  expected_id="${expected##*/}"; expected_id="${expected_id%-(latest)}"
  if [[ "$actual_id" == "$expected_id" ]]; then exit 0; fi
  # Keep family shorthand (e.g. deepseek); full model identifiers must match exactly.
  if [[ "$expected_id" != *-* && "$actual_id" == *"$expected_id"* ]]; then exit 0; fi
elif [[ "$model" == *"$expected"* ]]; then exit 0; fi
echo "MISMATCH: $target runs $kind $model, not $expected. Fix before the first prompt (see references/runtimes.md)." >&2
exit 1
