#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: bootstrap.sh [install|check|update] [--source <repo-root> | --repo <git-url>] [--ref <git-ref>] [--home <dir>]
Commands: install, check, update
Options: --source <path>, --repo <GitHub URL>, --ref <git-ref>, --home <dir>, -h|--help
USAGE
}
die() { echo "Error: $*" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || die "Python 3.11 or newer is required"
command_name=install
if [[ $# -gt 0 ]]; then case "$1" in install|check|update) command_name="$1"; shift ;; esac; fi
source_arg=""
local_source=false
repo_url="${ORCH_REPO:-https://github.com/smkamranqadri/orch-skill.git}"
repo_ref="${ORCH_REF:-main}"
home_dir="${HOME:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; local_source=true; shift 2 ;;
    --repo) [[ $# -ge 2 ]] || die "--repo requires a git URL"; repo_url="$2"; shift 2 ;;
    --ref) [[ $# -ge 2 ]] || die "--ref requires a git ref"; repo_ref="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ -n "$home_dir" ]] || die "HOME is unset; pass --home <dir>"
command -v herdr >/dev/null 2>&1 || die "herdr is required"
home_dir="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$home_dir")"
plugin_spec=""
if [[ "$local_source" != true ]]; then
  if [[ "$command_name" == update && "$repo_ref" != main ]]; then
    die "Herdr plugin update cannot pin --ref; use install to apply this ref"
  fi
  plugin_spec="$(python3 - "$repo_url" <<'PY'
import sys
from urllib.parse import urlparse
value = sys.argv[1]
if "://" in value:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.query or parsed.fragment:
        raise SystemExit(1)
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
else:
    parts = value.strip("/").removesuffix(".git").split("/")
if len(parts) != 2 or not all(parts) or any(part in (".", "..") for part in parts):
    raise SystemExit(1)
print("/".join(parts) + "/plugin")
PY
)" || die "Herdr plugin install requires a GitHub OWNER/REPO source"
fi
tmp_dir=""
rollback_tmp=""
cleanup() {
  [[ -z "$tmp_dir" ]] || rm -rf -- "$tmp_dir"
  [[ -z "$rollback_tmp" ]] || rm -rf -- "$rollback_tmp"
}
trap cleanup EXIT
if [[ -z "$source_arg" ]]; then
  command -v git >/dev/null 2>&1 || die "git is required for a release install"
  tmp_dir="$(mktemp -d)"
  git clone --depth 1 --branch "$repo_ref" "$repo_url" "$tmp_dir/orch-skill" >/dev/null || die "could not fetch source repository"
  source_arg="$tmp_dir/orch-skill"
fi
[[ -d "$source_arg" && -f "$source_arg/plugin/herdr-plugin.toml" ]] || die "source is not an orch-skill repository: $source_arg"
source_root="$(cd "$source_arg" && pwd -P)"

# Validate source, ownership, host destinations, and ancestors before calling Herdr.
source_preflight_mode=source-preflight
[[ "$command_name" != check ]] || source_preflight_mode=check-preflight
[[ "$command_name" != update ]] || source_preflight_mode=update-source-preflight
"$source_root/scripts/install-skill.sh" "$source_preflight_mode" --source "$source_root" --home "$home_dir" --plugin-dir "$source_root/plugin"

for destination in "$home_dir/.config/herdr" "$home_dir/.local/state/herdr"; do
  parent="$destination"
  while [[ "$parent" != "/" && "$parent" != "." ]]; do
    if [[ -e "$parent" || -L "$parent" ]]; then
      [[ -d "$parent" ]] || die "Herdr destination ancestor is not a directory: $parent"
      break
    fi
    parent="$(dirname "$parent")"
  done
done
export HOME="$home_dir"
export XDG_CONFIG_HOME="$home_dir/.config"
export XDG_STATE_HOME="$home_dir/.local/state"

prior_json="$(herdr plugin list --plugin orch --json)" || die "could not inspect the orch plugin before changes"
prior_plugin_dir=""
if [[ -n "$prior_json" ]]; then prior_plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$prior_json" 2>/dev/null || true)"; fi
# Resolve the existing CLI target and finish the read-only preflight before mutation.
preflight_mode=preflight
[[ "$command_name" != check ]] || preflight_mode=check-preflight
[[ "$command_name" != update ]] || preflight_mode=update-preflight
preflight_plugin_dir="$source_root/plugin"
[[ -z "$prior_plugin_dir" ]] || preflight_plugin_dir="$prior_plugin_dir"
"$source_root/scripts/install-skill.sh" "$preflight_mode" --source "$source_root" --home "$home_dir" --plugin-dir "$preflight_plugin_dir"
if [[ -n "$prior_plugin_dir" && -d "$prior_plugin_dir" ]]; then
  rollback_tmp="$(mktemp -d)"
  cp -a "$prior_plugin_dir" "$rollback_tmp/orch-plugin"
fi
herdr_changed=false
rollback_herdr() {
  [[ "$herdr_changed" == true ]] || return 0
  if [[ -n "$prior_plugin_dir" && -d "$prior_plugin_dir" ]]; then
    if [[ -d "$rollback_tmp/orch-plugin" ]]; then
      python3 - "$rollback_tmp/orch-plugin" "$prior_plugin_dir" <<'PY'
import shutil, sys
from pathlib import Path
source, target = map(Path, sys.argv[1:])
for entry in target.iterdir():
    if entry.is_dir() and not entry.is_symlink():
        shutil.rmtree(entry)
    else:
        entry.unlink()
for entry in source.iterdir():
    destination = target / entry.name
    if entry.is_dir() and not entry.is_symlink():
        shutil.copytree(entry, destination, symlinks=True)
    else:
        shutil.copy2(entry, destination, follow_symlinks=False)
PY
    fi
    herdr plugin link "$prior_plugin_dir" >/dev/null 2>&1 || true
  else
    herdr plugin unlink orch >/dev/null 2>&1 || true
  fi
}
on_exit() {
  local code=$?
  if [[ "$code" -ne 0 ]]; then rollback_herdr; fi
  cleanup
  exit "$code"
}
trap on_exit EXIT

if [[ "$command_name" == check ]]; then
  plugin_json="$prior_json"
  plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$plugin_json")" || die "Herdr did not report the installed orch plugin directory"
  if [[ "$local_source" == true && "$plugin_dir" != "$source_root/plugin" ]]; then die "Herdr orch plugin is not linked to this source checkout"; fi
  "$source_root/scripts/install-skill.sh" check --source "$source_root" --home "$home_dir" --plugin-dir "$plugin_dir"
else
  if [[ "$local_source" == true ]]; then
    herdr_changed=true
    herdr plugin link "$source_root/plugin"
    plugin_dir="$source_root/plugin"
  elif [[ "$command_name" == update ]]; then
    herdr_changed=true
    if herdr plugin update "$plugin_spec" --yes; then
      :
    else
      herdr plugin install "$plugin_spec" --ref "$repo_ref" --yes
    fi
    plugin_json="$(herdr plugin list --plugin orch --json)" || die "could not inspect the updated orch plugin"
    plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$plugin_json")" || die "Herdr did not report the installed orch plugin directory"
  else
    herdr_changed=true
    herdr plugin install "$plugin_spec" --ref "$repo_ref" --yes
    plugin_json="$(herdr plugin list --plugin orch --json)" || die "could not inspect the installed orch plugin"
    plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$plugin_json")" || die "Herdr did not report the installed orch plugin directory"
  fi
  "$source_root/scripts/install-skill.sh" "$command_name" --source "$source_root" --home "$home_dir" --plugin-dir "$plugin_dir"
fi
herdr_changed=false
cat <<'KEYS'
Note: Herdr's default sidebar key is also prefix+b.
Optional Herdr keybinding:
[[keys.command]]
key = "prefix+b"
type = "plugin_action"
command = "orch.board-full"
description = "Orch board, full screen"
KEYS
