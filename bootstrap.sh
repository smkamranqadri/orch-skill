#!/usr/bin/env bash
# Install, check, or update the orch skill and Herdr plugin.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bootstrap.sh [install|check|update] [--source <repo-root> | --repo <git-url>] [--ref <git-ref>] [--home <dir>]

Commands:
  install  Install the skill and plugin (default).
  check    Compare installed skill, host commands, and CLI links with the source.
  update   Update the skill and refresh the plugin installation.

Options:
  --source <path>  Local source checkout; links the local plugin.
  --repo <url>     Git repository for a release install. Defaults to orch-skill on GitHub.
  --ref <ref>      Git ref to fetch; defaults to main.
  --home <dir>     Home directory. Defaults to $HOME.
  -h, --help       Show this help.

Examples:
  ./bootstrap.sh install --source .
  ./bootstrap.sh install
  ./bootstrap.sh check --source .
  ./bootstrap.sh update --source .
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11 or newer is required"

command_name="install"
if [[ $# -gt 0 ]]; then
  case "$1" in install|check|update) command_name="$1"; shift ;; esac
fi

source_arg=""
local_source="false"
repo_url="${ORCH_REPO:-https://github.com/smkamranqadri/orch-skill.git}"
repo_ref="${ORCH_REF:-main}"
home_dir="${HOME:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; local_source="true"; shift 2 ;;
    --repo) [[ $# -ge 2 ]] || die "--repo requires a git URL"; repo_url="$2"; shift 2 ;;
    --ref) [[ $# -ge 2 ]] || die "--ref requires a git ref"; repo_ref="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "$home_dir" ]] || die "HOME is unset; pass --home <dir>"
command -v herdr >/dev/null 2>&1 || die "herdr is required"
home_dir="$(mkdir -p "$home_dir" && cd "$home_dir" && pwd -P)"

tmp_dir=""
cleanup() { [[ -z "$tmp_dir" ]] || rm -rf "$tmp_dir"; }
trap cleanup EXIT
if [[ -z "$source_arg" ]]; then
  command -v git >/dev/null 2>&1 || die "git is required for a release install"
  tmp_dir="$(mktemp -d)"
  git clone --depth 1 --branch "$repo_ref" "$repo_url" "$tmp_dir/orch-skill" >/dev/null \
    || die "could not fetch source repository"
  source_arg="$tmp_dir/orch-skill"
fi
[[ -d "$source_arg/skills/orch" && -f "$source_arg/plugin/herdr-plugin.toml" ]] \
  || die "source is not an orch-skill repository: $source_arg"
source_root="$(cd "$source_arg" && pwd -P)"

if [[ "$command_name" == check ]]; then
  plugin_json="$(herdr plugin list --plugin orch --json)" || die "could not inspect the orch plugin"
  plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$plugin_json")" \
    || die "Herdr did not report the installed orch plugin directory"
  if [[ "$local_source" == true && "$plugin_dir" != "$source_root/plugin" ]]; then
    die "Herdr orch plugin is not linked to this source checkout"
  fi
else
  if [[ "$local_source" == true ]]; then
    herdr plugin link "$source_root/plugin"
    plugin_dir="$source_root/plugin"
  else
    if [[ "$command_name" == update ]]; then
      if ! herdr plugin update orch --yes; then
        herdr plugin install smkamranqadri/orch-skill/plugin --yes
      fi
    else
      herdr plugin install smkamranqadri/orch-skill/plugin --yes
    fi
    plugin_json="$(herdr plugin list --plugin orch --json)" || die "could not inspect the installed orch plugin"
    plugin_dir="$(python3 "$source_root/scripts/plugin-path.py" <<<"$plugin_json")" \
      || die "Herdr did not report the installed orch plugin directory"
  fi
fi

install_args=("$command_name" --source "$source_root" --home "$home_dir" --plugin-dir "$plugin_dir")
"$source_root/scripts/install-skill.sh" "${install_args[@]}"

cat <<'KEYS'
Note: Herdr's default sidebar key is also prefix+b.
Optional Herdr keybinding:
[[keys.command]]
key = "prefix+b"
type = "plugin_action"
command = "orch.board-full"
description = "Orch board, full screen"
KEYS
