#!/usr/bin/env bash
# Install the orch skill and host command links from a source checkout.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh [install|check|update] --source <repo-root> --plugin-dir <plugin-dir> [--home <dir>]

Options:
  --source <path>      Source repository containing skills/orch/.
  --plugin-dir <path>  Installed or linked Herdr plugin directory containing orch.
  --home <dir>         Home directory. Defaults to $HOME.
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11 or newer is required"

mode="install"
if [[ $# -gt 0 ]]; then
  case "$1" in install|check|update) mode="$1"; shift ;; esac
fi
source_arg=""
plugin_arg=""
home_dir="${HOME:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; shift 2 ;;
    --plugin-dir) [[ $# -ge 2 ]] || die "--plugin-dir requires a path"; plugin_arg="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "$source_arg" && -d "$source_arg/skills/orch" ]] || die "source must contain skills/orch"
[[ -n "$plugin_arg" && -f "$plugin_arg/herdr-plugin.toml" && -x "$plugin_arg/orch" ]] \
  || die "plugin-dir must contain herdr-plugin.toml and executable orch"
[[ -n "$home_dir" ]] || die "HOME is unset; pass --home <dir>"
source_root="$(cd "$source_arg" && pwd -P)"
plugin_dir="$(cd "$plugin_arg" && pwd -P)"
home_dir="$(mkdir -p "$home_dir" && cd "$home_dir" && pwd -P)"

skill_source="$source_root/skills/orch"
agents_dir="$home_dir/.agents/skills"
skill_dest="$agents_dir/orch"
claude_skill="$home_dir/.claude/skills/orch"
claude_commands="$home_dir/.claude/commands/orch"
codex_prompts="$home_dir/.codex/prompts"
cli_dir="$home_dir/.local/bin"
cli_dest="$cli_dir/orch"
cli_source="$plugin_dir/orch"

owned_skill() {
  [[ -f "$1/.orch-install.json" ]] && python3 - "$1/.orch-install.json" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if data.get("managed_by") == "orch-bootstrap" else 1)
PY
}

same_link() { [[ -L "$1" && "$(readlink "$1")" == "$2" ]]; }

if [[ "$mode" == check ]]; then
  [[ -d "$skill_dest" ]] || die "orch skill is missing at $skill_dest"
  owned_skill "$skill_dest" || die "refusing to inspect an unowned skill at $skill_dest"
  diff -rq --exclude=.orch-install.json --exclude=__pycache__ --exclude=.DS_Store "$skill_source" "$skill_dest" >/dev/null \
    || die "installed orch skill differs from source"
  same_link "$claude_skill" "../../.agents/skills/orch" || die "Claude skill link is missing or differs"
  same_link "$claude_commands" "../../.agents/skills/orch/commands" || die "Claude command link is missing or differs"
  for command in start plan act close model; do
    same_link "$codex_prompts/orch-$command.md" "../../.agents/skills/orch/commands/$command.md" \
      || die "Codex prompt link is missing or differs: orch-$command"
  done
  same_link "$cli_dest" "$cli_source" || die "orch CLI link is missing or differs"
  echo "Orch skill and command links are current."
  exit 0
fi

if [[ -e "$skill_dest" || -L "$skill_dest" ]]; then
  owned_skill "$skill_dest" || die "refusing to overwrite a foreign path at $skill_dest"
  if diff -rq --exclude=.orch-install.json --exclude=__pycache__ --exclude=.DS_Store "$skill_source" "$skill_dest" >/dev/null; then
    skill_needs_update=false
  elif [[ "$mode" == update ]]; then
    skill_needs_update=true
  else
    die "installed orch differs; run bootstrap.sh update"
  fi
else
  skill_needs_update=true
fi

# Preflight every host and PATH destination before writing any installed files.
for item in \
  "$claude_skill|../../.agents/skills/orch" \
  "$claude_commands|../../.agents/skills/orch/commands"; do
  path="${item%%|*}"; target="${item#*|}"
  if [[ -e "$path" || -L "$path" ]]; then
    same_link "$path" "$target" || die "refusing to overwrite existing path: $path"
  fi
done
for command in start plan act close model; do
  path="$codex_prompts/orch-$command.md"
  if [[ -e "$path" || -L "$path" ]]; then
    same_link "$path" "../../.agents/skills/orch/commands/$command.md" \
      || die "refusing to overwrite existing path: $path"
  fi
done
if [[ -e "$cli_dest" || -L "$cli_dest" ]]; then
  same_link "$cli_dest" "$cli_source" || die "refusing to overwrite existing path: $cli_dest"
fi

if [[ "$skill_needs_update" == true ]]; then
  mkdir -p "$agents_dir"
  if [[ -d "$skill_dest" ]]; then
    backup="$home_dir/.agents/orch-backup-$(date +%Y%m%d-%H%M%S).tgz"
    tar -czf "$backup" -C "$agents_dir" orch
    echo "Backed up previous orch skill to $backup"
  fi
  temp_dir="$(mktemp -d "$agents_dir/.orch.XXXXXX")"
  trap 'rm -rf "$temp_dir"' EXIT
  cp -R "$skill_source/." "$temp_dir/"
  printf '{"managed_by":"orch-bootstrap","source":"%s"}\n' "$source_root" > "$temp_dir/.orch-install.json"
  rm -rf "$skill_dest"
  mv "$temp_dir" "$skill_dest"
  trap - EXIT
  echo "Installed orch skill -> $skill_dest"
else
  echo "Orch skill already current: $skill_dest"
fi

mkdir -p "$(dirname "$claude_skill")" "$(dirname "$claude_commands")" "$codex_prompts" "$cli_dir"
for item in \
  "$claude_skill|../../.agents/skills/orch" \
  "$claude_commands|../../.agents/skills/orch/commands"; do
  path="${item%%|*}"; target="${item#*|}"
  if ! same_link "$path" "$target"; then ln -s "$target" "$path"; fi
done
for command in start plan act close model; do
  path="$codex_prompts/orch-$command.md"
  target="../../.agents/skills/orch/commands/$command.md"
  if ! same_link "$path" "$target"; then ln -s "$target" "$path"; fi
done
if ! same_link "$cli_dest" "$cli_source"; then ln -s "$cli_source" "$cli_dest"; fi
echo "Orch CLI link: $cli_dest -> $cli_source"
