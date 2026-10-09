#!/usr/bin/env bash
# One-command install, check and update of the orch and session-close skills into a home.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  bootstrap.sh [install|check|update] [options]

Commands:
  install  Install the skills into ~/.agents/skills (default), then check Herdr.
  check    Report whether the installed skills differ from the source, then check Herdr.
  update   Replace the installed skills with the source when they differ (backup kept).
  doctor   Check Herdr only: the herdr binary and the Herdr agent skill.

Options:
  --repo <git-url>   Repository to clone as the source. Also ORCH_SKILL_REPO.
  --ref <git-ref>    Git ref to install from. Defaults to main. Also ORCH_SKILL_REF.
  --source <path>    Local source repo root. Skips the clone.
  --home <dir>       Home directory to install into. Defaults to $HOME.
  --force            install: replace an existing install.
  --no-claude-link   Do not create ~/.claude/commands/orch.
  --only <name>      Act on one skill only (orch or session-close). Repeatable.
  --with-herdr       Install what the Herdr check finds missing: the binary with the official
                     installer (network), the skill from `herdr --skill` (no network).
  --no-herdr         Skip the Herdr check.
  -h, --help         Show this help.

Examples:
  bootstrap.sh install --repo https://github.com/OWNER/orch-skill.git
  bootstrap.sh check --source ~/Repositores/side-projects/orch-skill
  bootstrap.sh update --source ~/Repositores/side-projects/orch-skill
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

command_name="install"
if [[ $# -gt 0 ]]; then
  case "$1" in install|check|update|doctor) command_name="$1"; shift ;; esac
fi

repo_url="${ORCH_SKILL_REPO:-}"
repo_ref="${ORCH_SKILL_REF:-main}"
source_arg=""
home_dir="${HOME:-}"
force="false"
claude_link="true"
with_herdr="false"
herdr_check="true"
only=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) [[ $# -ge 2 ]] || die "--repo requires a git URL"; repo_url="$2"; shift 2 ;;
    --ref) [[ $# -ge 2 ]] || die "--ref requires a git ref"; repo_ref="$2"; shift 2 ;;
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    --force) force="true"; shift ;;
    --no-claude-link) claude_link="false"; shift ;;
    --only) [[ $# -ge 2 ]] || die "--only requires a skill name"; only+=("$2"); shift 2 ;;
    --with-herdr) with_herdr="true"; shift ;;
    --no-herdr) herdr_check="false"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

# orch drives agents through Herdr (https://herdr.dev): a binary on PATH and an agent skill
# named herdr. Report what is missing; install only when asked with --with-herdr.
herdr_doctor() {
  local rc=0 skill="$home_dir/.agents/skills/herdr/SKILL.md"
  if command -v herdr >/dev/null 2>&1; then
    echo "Herdr binary: $(herdr --version 2>/dev/null || echo present)"
  elif [[ "$with_herdr" == "true" ]]; then
    echo "Herdr binary: missing; installing with the official script (network)"
    curl -fsSL https://herdr.dev/install.sh | sh || die "Herdr install failed"
    command -v herdr >/dev/null 2>&1 || die "herdr is still not on PATH; open a new shell and rerun"
    echo "Herdr binary: $(herdr --version 2>/dev/null || echo installed)"
  else
    echo "Herdr binary: missing. Install with one of:"
    echo "    curl -fsSL https://herdr.dev/install.sh | sh"
    echo "    brew install herdr"
    echo "  or rerun with --with-herdr."
    rc=1
  fi
  if [[ -f "$skill" ]]; then
    if command -v herdr >/dev/null 2>&1 && ! herdr --skill 2>/dev/null | diff -q - "$skill" >/dev/null; then
      if [[ "$with_herdr" == "true" ]]; then
        herdr --skill > "$skill" || die "herdr --skill failed"
        echo "Herdr skill: was stale, refreshed from 'herdr --skill' at $skill"
      else
        echo "Herdr skill: STALE at $skill (differs from the copy bundled in $(herdr --version 2>/dev/null)); refresh with: herdr --skill > $skill, or rerun with --with-herdr"
        rc=1
      fi
    else
      echo "Herdr skill: $skill"
    fi
  elif [[ "$with_herdr" == "true" ]] && command -v herdr >/dev/null 2>&1; then
    mkdir -p "$(dirname "$skill")"
    herdr --skill > "$skill" || die "herdr --skill failed"
    [[ -s "$skill" ]] || die "herdr --skill printed nothing"
    echo "Herdr skill: written from 'herdr --skill' to $skill"
  else
    echo "Herdr skill: missing. Install with one of:"
    echo "    npx skills add herdrdev/herdr --skill herdr -g"
    echo "    herdr --skill > $skill   (with the binary installed)"
    echo "  or rerun with --with-herdr."
    rc=1
  fi
  return $rc
}

if [[ "$command_name" == "doctor" ]]; then
  [[ -n "$home_dir" ]] || die "missing --home <dir> and HOME is unset"
  home_dir="$(mkdir -p "$home_dir" && cd "$home_dir" && pwd -P)"
  herdr_doctor
  exit $?
fi

if [[ -z "$source_arg" ]]; then
  [[ -n "$repo_url" ]] || die "missing --repo <git-url>, ORCH_SKILL_REPO, or --source <path>"
  command -v git >/dev/null 2>&1 || die "git is required when using --repo"
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT
  git clone --depth 1 --branch "$repo_ref" "$repo_url" "$tmp_dir/orch-skill" >/dev/null
  source_arg="$tmp_dir/orch-skill"
fi
[[ -d "$source_arg/skills" ]] || die "source is not an orch-skill repo root: $source_arg"
source_root="$(cd "$source_arg" && pwd -P)"
[[ -n "$home_dir" ]] || die "missing --home <dir> and HOME is unset"
home_dir="$(mkdir -p "$home_dir" && cd "$home_dir" && pwd -P)"

install_args=(--source "$source_root" --home "$home_dir")
[[ "$claude_link" == "false" ]] && install_args+=(--no-claude-link)
for o in ${only[@]+"${only[@]}"}; do install_args+=(--only "$o"); done

selected() {
  local name="$1"
  [[ ${#only[@]} -eq 0 ]] && return 0
  local o; for o in "${only[@]}"; do [[ "$o" == "$name" ]] && return 0; done
  return 1
}

# Prints one line per skill: "<name> current|differs|missing"
compare() {
  local src name dest status
  for src in "$source_root"/skills/*/; do
    name="$(basename "$src")"
    selected "$name" || continue
    dest="$home_dir/.agents/skills/$name"
    if [[ ! -d "$dest" ]]; then
      status="missing"
    elif diff -rq --exclude=__pycache__ --exclude=.DS_Store "$src" "$dest" >/dev/null; then
      status="current"
    else
      status="differs"
    fi
    echo "$name $status"
  done
}

case "$command_name" in
  install)
    args=("${install_args[@]}")
    [[ "$force" == "true" ]] && args+=(--force)
    "$source_root/scripts/install-skill.sh" "${args[@]}"
    [[ "$herdr_check" == "true" ]] && herdr_doctor || true
    ;;
  check)
    rc=0
    while read -r name status; do
      case "$status" in
        current) echo "Already current: $name" ;;
        differs) echo "Update available: $name (installed copy differs from source)"; rc=1 ;;
        missing) echo "Not installed: $name"; rc=1 ;;
      esac
    done < <(compare)
    if [[ "$herdr_check" == "true" ]]; then herdr_doctor || rc=1; fi
    exit $rc
    ;;
  update)
    while read -r name status; do
      case "$status" in
        current) echo "Already current: $name" ;;
        differs|missing)
          args=(--source "$source_root" --home "$home_dir" --only "$name" --force)
          [[ "$claude_link" == "false" ]] && args+=(--no-claude-link)
          "$source_root/scripts/install-skill.sh" "${args[@]}"
          ;;
      esac
    done < <(compare)
    [[ "$herdr_check" == "true" ]] && herdr_doctor || true
    ;;
esac
