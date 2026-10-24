#!/usr/bin/env bash
# Install the orch skill and host command links from a source checkout.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh [preflight|install|check|update] --source <repo-root> --plugin-dir <plugin-dir> [--home <dir>]

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
  case "$1" in preflight|update-preflight|check-preflight|source-preflight|update-source-preflight|install|check|update) mode="$1"; shift ;; esac
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

[[ -n "$source_arg" && -d "$source_arg" ]] || die "source must contain skills/orch and a complete command set"
[[ -n "$plugin_arg" && -f "$plugin_arg/herdr-plugin.toml" && -x "$plugin_arg/orch" ]] \
  || die "plugin-dir must contain herdr-plugin.toml and executable orch"
[[ -n "$home_dir" ]] || die "HOME is unset; pass --home <dir>"
source_root="$(cd "$source_arg" && pwd -P)"
plugin_dir="$(cd "$plugin_arg" && pwd -P)"
home_dir="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$home_dir")"

skill_source="$source_root/skills/orch"
agents_dir="$home_dir/.agents/skills"
skill_dest="$agents_dir/orch"
claude_skill="$home_dir/.claude/skills/orch"
claude_commands="$home_dir/.claude/commands/orch"
codex_prompts="$home_dir/.codex/prompts"
cli_dir="$home_dir/.local/bin"
cli_dest="$cli_dir/orch"
cli_source="$plugin_dir/orch"
commands=(start plan act close model)

validate_source() {
  python3 - "$source_root" <<'PY'
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

root = Path(sys.argv[1])
required = [root / "skills/orch/SKILL.md"]
required.extend(root / "skills/orch/commands" / f"{name}.md" for name in ("start", "plan", "act", "close", "model"))
required.append(root / "skills/orch/references/matrix.md")
required.append(root / "skills/orch/references/proof.md")
missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
if missing:
    print("incomplete orch skill source: missing " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
for document in required:
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        target = target.strip().split()[0].strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or target.startswith("#"):
            continue
        local = (document.parent / parsed.path).resolve()
        if parsed.path and not local.exists():
            print(f"incomplete orch skill source: {document.relative_to(root)} references missing {target}", file=sys.stderr)
            raise SystemExit(1)
PY
}

owned_skill() {
  [[ ! -L "$1" && -d "$1" && -f "$1/.orch-install.json" ]] && python3 - "$1/.orch-install.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as marker:
        data = json.load(marker)
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if data.get("managed_by") == "orch-bootstrap" else 1)
PY
}

same_link() { [[ -L "$1" && "$(readlink "$1")" == "$2" ]]; }
orch_cli_link() {
  [[ -L "$1" && -x "$1" ]] || return 1
  python3 - "$1" <<'PY'
import os, sys, tomllib
from pathlib import Path
try:
    executable = Path(sys.argv[1]).resolve(strict=True)
    with (executable.parent / "herdr-plugin.toml").open("rb") as manifest:
        data = tomllib.load(manifest)
except (OSError, RuntimeError, tomllib.TOMLDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if executable.is_file() and os.access(executable, os.X_OK) and data.get("id") == "orch" else 1)
PY
}

# Confirm every existing ancestor is a directory and the leaf is either owned or exactly ours.
check_parent_chain() {
  local path="$1" parent
  parent="$(dirname "$path")"
  while [[ "$parent" != "/" && "$parent" != "." ]]; do
    if [[ -e "$parent" || -L "$parent" ]]; then
      [[ -d "$parent" ]] || die "destination ancestor is not a directory: $parent"
      return 0
    fi
    path="$parent"
    parent="$(dirname "$path")"
  done
}

preflight() {
  validate_source || die "source validation failed"
  check_parent_chain "$skill_dest"
  if [[ "$mode" != check && "$mode" != check-preflight && ( -e "$skill_dest" || -L "$skill_dest" ) ]]; then
    owned_skill "$skill_dest" || die "refusing to overwrite a foreign path at $skill_dest"
    if ! diff -rq --exclude=.orch-install.json --exclude=__pycache__ --exclude=.DS_Store "$skill_source" "$skill_dest" >/dev/null; then
      [[ "$mode" == update || "$mode" == update-preflight || "$mode" == update-source-preflight ]] || die "installed orch skill differs from source"
    fi
  fi
  local path expected command
  for path_expected in \
    "$claude_skill|../../.agents/skills/orch" \
    "$claude_commands|../../.agents/skills/orch/commands"; do
    path="${path_expected%%|*}"; expected="${path_expected#*|}"
    check_parent_chain "$path"
    if [[ "$mode" != check && "$mode" != check-preflight && ( -e "$path" || -L "$path" ) ]]; then
      same_link "$path" "$expected" || die "refusing to overwrite existing path: $path"
    fi
  done
  for command in "${commands[@]}"; do
    path="$codex_prompts/orch-$command.md"
    check_parent_chain "$path"
    if [[ "$mode" != check && "$mode" != check-preflight && ( -e "$path" || -L "$path" ) ]]; then
      same_link "$path" "../../.agents/skills/orch/commands/$command.md" \
        || die "refusing to overwrite existing path: $path"
    fi
  done
  check_parent_chain "$cli_dest"
  if [[ "$mode" == source-preflight && ( -e "$cli_dest" || -L "$cli_dest" ) ]]; then
    [[ -L "$cli_dest" && -x "$cli_dest" ]] || die "refusing to overwrite existing path: $cli_dest"
  elif [[ "$mode" != check && "$mode" != check-preflight && "$mode" != source-preflight && ( -e "$cli_dest" || -L "$cli_dest" ) ]]; then
    same_link "$cli_dest" "$cli_source" || orch_cli_link "$cli_dest" || die "refusing to overwrite existing path: $cli_dest"
  fi
}

preflight
[[ "$mode" != preflight ]] || { echo "Orch source and install destinations are ready."; exit 0; }
[[ "$mode" != update-preflight ]] || { echo "Orch source and update destinations are ready."; exit 0; }
[[ "$mode" != check-preflight ]] || { echo "Orch source and install ancestors are ready."; exit 0; }
[[ "$mode" != source-preflight ]] || { echo "Orch source, ownership, and host destinations are ready."; exit 0; }
[[ "$mode" != update-source-preflight ]] || { echo "Orch source and update destinations are ready."; exit 0; }

if [[ "$mode" == check ]]; then
  [[ -d "$skill_dest" ]] || die "orch skill is missing at $skill_dest"
  owned_skill "$skill_dest" || die "refusing to inspect an unowned skill at $skill_dest"
  diff -rq --exclude=.orch-install.json --exclude=__pycache__ --exclude=.DS_Store "$skill_source" "$skill_dest" >/dev/null \
    || die "installed orch skill differs from source"
  same_link "$claude_skill" "../../.agents/skills/orch" || die "Claude skill link is missing or differs"
  same_link "$claude_commands" "../../.agents/skills/orch/commands" || die "Claude command link is missing or differs"
  for command in "${commands[@]}"; do
    same_link "$codex_prompts/orch-$command.md" "../../.agents/skills/orch/commands/$command.md" \
      || die "Codex prompt link is missing or differs: orch-$command"
  done
  same_link "$cli_dest" "$cli_source" || die "orch CLI link is missing or differs"
  echo "Orch skill and command links are current."
  exit 0
fi

skill_needs_update=true
  if [[ -e "$skill_dest" || -L "$skill_dest" ]]; then
    owned_skill "$skill_dest" || die "refusing to inspect an unowned skill at $skill_dest"
  fi
  if [[ -d "$skill_dest" ]] && diff -rq --exclude=.orch-install.json --exclude=__pycache__ --exclude=.DS_Store "$skill_source" "$skill_dest" >/dev/null; then
  skill_needs_update=false
fi

created_dirs=()
created_links=()
replaced_links=()
replaced_targets=()
temp_dir=""
hold_dir=""
backup_tmp=""
backup_lock=""
skill_published=false
had_previous=false
cleanup() {
  local code=$?
  trap - EXIT
  if [[ "$code" -ne 0 ]]; then
    local link dir
    for link in "${created_links[@]}"; do rm -f -- "$link"; done
    for ((i=0; i<${#replaced_links[@]}; i++)); do
      rm -f -- "${replaced_links[i]}"
      ln -s "${replaced_targets[i]}" "${replaced_links[i]}" || true
    done
    if [[ "$skill_published" == true ]]; then rm -rf -- "$skill_dest"; fi
    if [[ "$had_previous" == true && -n "$hold_dir" && -d "$hold_dir" ]]; then mv -- "$hold_dir" "$skill_dest" || true; fi
  fi
  [[ -z "$temp_dir" ]] || rm -rf -- "$temp_dir"
  [[ -z "$backup_tmp" ]] || rm -f -- "$backup_tmp"
  [[ -z "$backup_lock" ]] || rmdir -- "$backup_lock" 2>/dev/null || true
  if [[ "$code" -ne 0 ]]; then
    for ((i=${#created_dirs[@]}-1; i>=0; i--)); do rmdir -- "${created_dirs[i]}" 2>/dev/null || true; done
  fi
  exit "$code"
}
trap cleanup EXIT

ensure_dir() {
  local dir="$1" parent
  [[ -d "$dir" ]] && return 0
  [[ ! -e "$dir" && ! -L "$dir" ]] || die "destination ancestor is not a directory: $dir"
  parent="$(dirname "$dir")"
  [[ "$parent" == "$dir" ]] || ensure_dir "$parent"
  mkdir -- "$dir"
  created_dirs+=("$dir")
}

for dir in "$home_dir" "$agents_dir" "$(dirname "$claude_skill")" "$(dirname "$claude_commands")" "$codex_prompts" "$cli_dir"; do
  ensure_dir "$dir"
done

if [[ "$skill_needs_update" == true ]]; then
  temp_dir="$(mktemp -d "$agents_dir/.orch.new.XXXXXX")"
  cp -R "$skill_source/." "$temp_dir/"
  python3 - "$temp_dir/.orch-install.json" "$source_root" <<'PY'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as marker:
    json.dump({"managed_by": "orch-bootstrap", "source": sys.argv[2]}, marker)
    marker.write("\n")
PY
  if [[ -d "$skill_dest" ]]; then
    had_previous=true
    hold_dir="$(mktemp -d "$agents_dir/.orch.old.XXXXXX")"
    rmdir "$hold_dir"
    stamp="$(date +%Y%m%d-%H%M%S)"
    suffix=0
    while :; do
      if [[ "$suffix" == 0 ]]; then
        backup="$home_dir/.agents/orch-backup-$stamp.tgz"
      else
        backup="$home_dir/.agents/orch-backup-$stamp-$suffix.tgz"
      fi
      backup_lock="$backup.reserve"
      if [[ ! -e "$backup" ]] && mkdir "$backup_lock" 2>/dev/null; then break; fi
      suffix=$((suffix + 1))
    done
    backup_tmp="$(mktemp "$home_dir/.agents/.orch-backup.XXXXXX.tmp")"
    tar -czf "$backup_tmp" -C "$agents_dir" orch
    ln "$backup_tmp" "$backup"
    rm "$backup_tmp"
    backup_tmp=""
    rmdir "$backup_lock"
    backup_lock=""
    echo "Backed up previous orch skill to $backup"
    mv "$skill_dest" "$hold_dir"
  fi
  mv "$temp_dir" "$skill_dest"
  temp_dir=""
  skill_published=true
  echo "Installed orch skill -> $skill_dest"
else
  echo "Orch skill already current: $skill_dest"
fi

link_if_missing() {
  local path="$1" target="$2"
  if ! same_link "$path" "$target"; then
    ln -s "$target" "$path"
    created_links+=("$path")
  fi
}
link_cli() {
  if same_link "$cli_dest" "$cli_source"; then return 0; fi
  if [[ -e "$cli_dest" || -L "$cli_dest" ]]; then
    orch_cli_link "$cli_dest" || die "refusing to overwrite existing path: $cli_dest"
    replaced_links+=("$cli_dest")
    replaced_targets+=("$(readlink "$cli_dest")")
    rm -- "$cli_dest"
    ln -s "$cli_source" "$cli_dest"
  else
    ln -s "$cli_source" "$cli_dest"
    created_links+=("$cli_dest")
  fi
}
link_if_missing "$claude_skill" "../../.agents/skills/orch"
link_if_missing "$claude_commands" "../../.agents/skills/orch/commands"
for command in "${commands[@]}"; do
  link_if_missing "$codex_prompts/orch-$command.md" "../../.agents/skills/orch/commands/$command.md"
done
link_cli

if [[ "$had_previous" == true ]]; then
  rm -rf -- "$hold_dir"
  had_previous=false
fi
skill_published=false
echo "Orch CLI link: $cli_dest -> $cli_source"
