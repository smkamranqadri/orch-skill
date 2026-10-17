#!/usr/bin/env bash
# Static start-cost probe: list the files each start or close path loads into an agent's context,
# with word counts and an estimated token count (words x 1.3). The numbers are estimates, not
# measured tokens; live token counts come from host transcripts. Run from a source clone only.
#
# Paths measured (baseline definitions, plan 2026-10-17 phase 0):
#   global:<host>     the host's global instruction file (one level of @imports) plus the repo's
#                     AGENTS.md and CLAUDE.md
#   anchor:kis        the KIS SessionStart anchor's output in the repo
#   kis:start         KIS start command plus kis/state/*.md
#   orch:start:light  orch SKILL.md, commands/start.md, kis/state/current.md
#   orch:start:heavy  light plus the ledger template, status, watch, runtimes, visibility,
#                     brief rules, placement and the Herdr skill
#   session-close     session-close SKILL.md plus KIS sync and check commands
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  measure-start.sh [--home <dir>] [--repo <dir>]

Options:
  --home <dir>   Home whose installed skills and global files are measured. Defaults to $HOME.
  --repo <dir>   Repo whose AGENTS.md, kis/ and vendored KIS are measured. Defaults to the cwd.
  -h, --help     Show this help.
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

home_dir="${HOME:-}"
repo_dir="$PWD"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    --repo) [[ $# -ge 2 ]] || die "--repo requires a path"; repo_dir="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[[ -d "$home_dir" ]] || die "home not found: $home_dir"
[[ -d "$repo_dir" ]] || die "repo not found: $repo_dir"
home_dir="$(cd "$home_dir" && pwd)"
repo_dir="$(cd "$repo_dir" && pwd)"

skills="$home_dir/.agents/skills"
kis="$repo_dir/.agents/skills/kis"

show() {
  local p="$1"
  local tilde='~'
  p="${p/#"$repo_dir"/<repo>}"
  printf '%s' "${p/#"$home_dir"/$tilde}"
}

est() { echo $(( ($1 * 13 + 5) / 10 )); }

path_name=""
path_words=0

begin() { path_name="$1"; path_words=0; }

row() {
  local label="$1" words="$2"
  printf '%s\t%s\t%s\t%s\n' "$path_name" "$label" "$words" "$(est "$words")"
  path_words=$(( path_words + words ))
}

file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    row "$(show "$f")" "$(wc -w < "$f" | tr -d ' ')"
  else
    printf '%s\t%s\tmissing\t0\n' "$path_name" "$(show "$f")"
  fi
}

# A global file plus the files it imports with a line of the form "@<path>".
global_file() {
  local f="$1" imp
  file "$f"
  [[ -f "$f" ]] || return 0
  while IFS= read -r imp; do
    imp="${imp#@}"
    imp="${imp/#\~/$home_dir}"
    file "$imp"
  done < <(grep -E '^@[^[:space:]]+$' "$f" || true)
}

end() {
  printf '%s\tTOTAL\t%s\t%s\n' "$path_name" "$path_words" "$(est "$path_words")"
}

repo_files() {
  file "$repo_dir/AGENTS.md"
  [[ -f "$repo_dir/CLAUDE.md" ]] && file "$repo_dir/CLAUDE.md"
  return 0
}

echo "# measure-start: static estimate (tokens = words x 1.3, not measured)"
echo "# home: $(show "$home_dir")  repo: $(basename "$repo_dir")"
printf 'path\tfile\twords\test_tokens\n'

for host in claude codex cmd agy; do
  begin "global:$host"
  case "$host" in
    claude) global_file "$home_dir/.claude/CLAUDE.md" ;;
    codex) global_file "$home_dir/.codex/AGENTS.md" ;;
    cmd) global_file "$home_dir/.commandcode/AGENTS.md" ;;
    agy) global_file "$home_dir/.gemini/GEMINI.md" ;;
  esac
  repo_files
  end
done

begin "anchor:kis"
anchor="$kis/hooks/session-anchor.sh"
if [[ -x "$anchor" ]]; then
  words="$(cd "$repo_dir" && CLAUDE_PROJECT_DIR="$repo_dir" HOME="$home_dir" "$anchor" </dev/null 2>/dev/null | wc -w | tr -d ' ')"
  row "$(show "$anchor") (output)" "$words"
else
  printf '%s\t%s\tmissing\t0\n' "$path_name" "$(show "$anchor")"
fi
end

begin "kis:start"
file "$kis/commands/start.md"
for f in "$repo_dir"/kis/state/*.md; do file "$f"; done
end

light() {
  file "$skills/orch/SKILL.md"
  file "$skills/orch/commands/start.md"
  file "$repo_dir/kis/state/current.md"
}

begin "orch:start:light"
light
end

begin "orch:start:heavy"
light
file "$skills/orch/ledger-template.md"
file "$skills/orch/commands/status.md"
file "$skills/orch/commands/watch.md"
for r in runtimes visibility brief-rules placement; do file "$skills/orch/references/$r.md"; done
file "$skills/herdr/SKILL.md"
end

begin "session-close"
file "$skills/session-close/SKILL.md"
file "$kis/commands/sync.md"
file "$kis/commands/check.md"
end
