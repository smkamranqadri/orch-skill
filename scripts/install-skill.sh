#!/usr/bin/env bash
# Install the skills in this repo (skills/*) into a user's home: ~/.agents/skills/<name>,
# plus Claude discovery links ~/.claude/skills/<name>, the command link ~/.claude/commands/orch,
# orch's four named sub-agent definitions ~/.claude/agents/<name>.md (copied, never overwritten),
# and orch's commands for the other hosts: Codex prompts, Command Code commands, an agy skill
# link. It also retires the session-close skill that orch:close replaced. Run from a source
# clone only.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh --source <repo-root> [--home <dir>] [--force] [--force-agents] [--no-claude-link]
                   [--agents-only|--wire-only] [--hosts <list>] [--only <name>]
  install-skill.sh --source <repo-root> [--home <dir>] [--hosts <list>] --report

Options:
  --source <path>    Source repo root containing skills/<name>/SKILL.md. Also ORCH_SKILL_SOURCE.
  --home <dir>       Home directory to install into. Defaults to $HOME.
  --force            Replace an existing ~/.agents/skills/<name> (a .tgz backup is kept).
  --force-agents     Replace a different ~/.claude/agents/<name>.md (copy kept in ~/.agents/).
                     Without it a different file is kept and reported, never overwritten.
  --no-claude-link   Skip ~/.claude/skills links, commands link and agent definitions.
  --agents-only      Install only the sub-agent definitions; leave the skills alone.
  --wire-only        Install only the retirement and the per-host wiring; leave the skills alone.
  --hosts <list>     Hosts to wire orch commands into besides Claude: auto (default: those whose
                     folder exists or whose binary is on PATH), all, none, or a comma list of
                     codex, cmd, agy.
  --report           Print one status line per host item and retired leftover; change nothing.
  --only <name>      Install only this skill (orch). Repeatable.
  -h, --help         Show this help.
USAGE
}

die() { echo "Error: $*" >&2; exit 1; }

source_arg="${ORCH_SKILL_SOURCE:-}"
home_dir="${HOME:-}"
force="false"
claude_link="true"
force_agents="false"
agents_only="false"
wire_only="false"
report="false"
hosts="auto"
only=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    --force) force="true"; shift ;;
    --force-agents) force_agents="true"; shift ;;
    --agents-only) agents_only="true"; shift ;;
    --wire-only) wire_only="true"; shift ;;
    --report) report="true"; shift ;;
    --hosts) [[ $# -ge 2 ]] || die "--hosts requires auto, all, none or a list"; hosts="$2"; shift 2 ;;
    --no-claude-link) claude_link="false"; shift ;;
    --only) [[ $# -ge 2 ]] || die "--only requires a skill name"; only+=("$2"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "$source_arg" ]] || die "missing --source <repo-root> or ORCH_SKILL_SOURCE"
[[ -n "$home_dir" ]] || die "missing --home <dir> and HOME is unset"
[[ -d "$source_arg/skills" ]] || die "source is not an orch-skill repo root (no skills/): $source_arg"
source_root="$(cd "$source_arg" && pwd -P)"
home_dir="$(mkdir -p "$home_dir" && cd "$home_dir" && pwd -P)"

read_version() {
  ruby -ryaml -e '
    text = File.read(File.join(ARGV.fetch(0), "SKILL.md"))
    fm = text[/\A---\n(.*?)\n---\n/m, 1] or abort("missing YAML frontmatter in #{ARGV[0]}/SKILL.md")
    data = YAML.safe_load(fm)
    abort("frontmatter must be a map") unless data.is_a?(Hash)
    abort("missing name") if data["name"].to_s.strip.empty?
    abort("invalid name") unless data["name"].match?(/\A[a-z0-9-]+\z/)
    abort("missing description") if data["description"].to_s.strip.empty?
    v = data.dig("metadata", "version")
    abort("missing metadata.version in #{ARGV[0]}/SKILL.md") if v.to_s.strip.empty?
    puts v
  ' "$1"
}

wanted() {
  local name="$1"
  [[ ${#only[@]} -eq 0 ]] && return 0
  local o; for o in "${only[@]}"; do [[ "$o" == "$name" ]] && return 0; done
  return 1
}

skills_dir="$home_dir/.agents/skills"

# --- retirement of session-close (replaced by orch:close) ---------------------------------
# The installer removes only what it shipped: the discovery links with their exact shipped
# targets, and the package when it is one SKILL.md whose sha256 is a version this repo shipped
# (1.0.0, 1.0.1, 1.0.2). Anything else is the user's and is kept and reported.
retired_hashes="3de7cc86230eb354ff60f84b2280a17facb5a3c028f5d749a4c5d820ab75a525 7feedfd1560e54a02cd86786878400941d1b52b5a0d7a5787caf90ea3960948c 2539ed9151a951dbe3330fabf3ecd9604674602e1bfd188176c1dea9867829bb"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# Prints "<path>\t<expected link target>" per retired discovery link location.
retired_link_paths() {
  [[ "$claude_link" == "true" ]] && printf '%s\t%s\n' "$home_dir/.claude/skills/session-close" "../../.agents/skills/session-close"
  printf '%s\t%s\n' "$home_dir/.gemini/config/skills/session-close" "../../../.agents/skills/session-close"
  return 0
}

# "gone", "ours" (exactly what was shipped) or "foreign" for a retired link path.
retired_link_state() {
  local path="$1" target="$2"
  if [[ ! -e "$path" && ! -L "$path" ]]; then echo gone
  elif [[ -L "$path" && "$(readlink "$path")" == "$target" ]]; then echo ours
  else echo foreign; fi
}

# "gone", "ours" (shipped, unmodified) or "foreign" for the retired package.
retired_package_state() {
  local dest="$skills_dir/session-close" h
  if [[ ! -e "$dest" && ! -L "$dest" ]]; then echo gone; return; fi
  if [[ -L "$dest" || ! -d "$dest" || ! -f "$dest/SKILL.md" ]]; then echo foreign; return; fi
  [[ "$(find "$dest" -mindepth 1 | wc -l | tr -d ' ')" == 1 ]] || { echo foreign; return; }
  h="$(sha256_of "$dest/SKILL.md")"
  [[ " $retired_hashes " == *" $h "* ]] && echo ours || echo foreign
}

retire_session_close() {
  local path target state
  while IFS=$'\t' read -r path target; do
    state="$(retired_link_state "$path" "$target")"
    case "$state" in
      ours) rm -f "$path"; echo "Retired session-close link: $path" ;;
      foreign) echo "Kept $path (not the link orch shipped for session-close; remove it by hand)" ;;
    esac
  done < <(retired_link_paths)
  case "$(retired_package_state)" in
    ours) rm -rf "$skills_dir/session-close"; echo "Retired session-close package: $skills_dir/session-close" ;;
    foreign) echo "Kept $skills_dir/session-close (modified or not shipped by orch; orch:close replaces it, remove it by hand)" ;;
  esac
}

# --- per-host wiring of the orch commands ---------------------------------------------------
# Claude: ~/.claude/commands/orch -> the commands folder (/orch:start, /orch:close).
# Codex: ~/.codex/prompts/orch-<name>.md copies (/prompts:orch-start). Command Code:
# ~/.commandcode/commands/orch-<name>.md copies (/orch-start). agy has no custom slash commands:
# it discovers the orch skill through ~/.gemini/config/skills/orch and runs a command by name
# ("run the orch start step"). Copies carry no link into the package, so check compares bytes.
real_home="$(cd "${HOME:-/}" 2>/dev/null && pwd -P || true)"
codex_home="$home_dir/.codex"
if [[ -n "${CODEX_HOME:-}" && "$home_dir" == "$real_home" ]]; then codex_home="$CODEX_HOME"; fi
cmd_dir="$home_dir/.commandcode/commands"
codex_dir="$codex_home/prompts"
agy_link="$home_dir/.gemini/config/skills/orch"
agy_target="../../../.agents/skills/orch"

host_on() {
  case "$hosts" in
    all) return 0 ;;
    none) return 1 ;;
    auto)
      case "$1" in
        codex) [[ -d "$codex_home" ]] || command -v codex >/dev/null 2>&1 ;;
        cmd) [[ -d "$home_dir/.commandcode" ]] || command -v cmd >/dev/null 2>&1 ;;
        agy) [[ -d "$home_dir/.gemini" ]] || command -v agy >/dev/null 2>&1 ;;
        *) return 1 ;;
      esac ;;
    *) [[ ",$hosts," == *",$1,"* ]] ;;
  esac
}

command_files() { local f; for f in "$source_root"/skills/orch/commands/*.md; do [[ -f "$f" ]] && echo "$f"; done; return 0; }

copy_state() {  # <source file> <dest file>: current | differs | missing
  if [[ ! -e "$2" && ! -L "$2" ]]; then echo missing
  elif [[ -f "$2" && ! -L "$2" ]] && cmp -s "$1" "$2"; then echo current
  else echo differs; fi
}

install_command_copies() {  # <label: "Codex prompt" | "Command Code command"> <dest dir>
  local label="$1" dir="$2" f dest state
  mkdir -p "$dir"
  while IFS= read -r f; do
    dest="$dir/orch-$(basename "$f")"
    state="$(copy_state "$f" "$dest")"
    case "$state" in
      current) echo "$label already current: $dest" ;;
      missing) cp "$f" "$dest"; echo "$label installed: $dest" ;;
      differs)
        if [[ -f "$dest" && ! -L "$dest" ]]; then cp "$f" "$dest"; echo "$label updated: $dest"
        else echo "Kept your existing $label path: $dest (not a plain file; not overwritten)"; fi ;;
    esac
  done < <(command_files)
}

agy_link_state() {
  if [[ -L "$agy_link" ]] && [[ "$(readlink "$agy_link")" == "$agy_target" ]]; then echo current
  elif [[ -e "$agy_link" || -L "$agy_link" ]]; then echo differs
  else echo missing; fi
}

install_agy_link() {
  case "$(agy_link_state)" in
    current) echo "agy skill link already current: $agy_link" ;;
    missing)
      mkdir -p "$(dirname "$agy_link")"
      ln -s "$agy_target" "$agy_link"
      echo "agy skill link: $agy_link -> $agy_target" ;;
    differs) echo "Kept your existing agy skill path: $agy_link (not overwritten)" ;;
  esac
}

wire_hosts() {
  if host_on codex; then
    install_command_copies "Codex prompt" "$codex_dir"
    echo "Codex usage: /prompts:orch-start /prompts:orch-close (custom prompts are deprecated upstream; the orch skill in ~/.agents/skills also loads by name)"
  else echo "Codex commands: skipped (not installed; --hosts all forces)"; fi
  if host_on cmd; then
    install_command_copies "Command Code command" "$cmd_dir"
    echo "Command Code usage: /orch-start /orch-close"
  else echo "Command Code commands: skipped (not installed; --hosts all forces)"; fi
  if host_on agy; then
    install_agy_link
    echo "agy usage: no custom slash commands; say \"run the orch start step\" or \"run the orch close step\""
  else echo "agy skill link: skipped (not installed; --hosts all forces)"; fi
}

# Tab-separated lines: "<host>\t<path>\t<current|differs|missing>" per wired item, and
# "retired\t<link|package>\t<path>\t<ours|foreign>" per leftover of session-close. Hosts that are
# not selected print nothing. Changes nothing.
report_wiring() {
  local f dest path target state
  if host_on codex; then
    while IFS= read -r f; do dest="$codex_dir/orch-$(basename "$f")"; printf 'codex\t%s\t%s\n' "$dest" "$(copy_state "$f" "$dest")"; done < <(command_files)
  fi
  if host_on cmd; then
    while IFS= read -r f; do dest="$cmd_dir/orch-$(basename "$f")"; printf 'cmd\t%s\t%s\n' "$dest" "$(copy_state "$f" "$dest")"; done < <(command_files)
  fi
  if host_on agy; then printf 'agy\t%s\t%s\n' "$agy_link" "$(agy_link_state)"; fi
  while IFS=$'\t' read -r path target; do
    state="$(retired_link_state "$path" "$target")"
    [[ "$state" == gone ]] || printf 'retired\tlink\t%s\t%s\n' "$path" "$state"
  done < <(retired_link_paths)
  state="$(retired_package_state)"
  [[ "$state" == gone ]] || printf 'retired\tpackage\t%s\t%s\n' "$skills_dir/session-close" "$state"
  return 0
}

if [[ "$report" == "true" ]]; then report_wiring; exit 0; fi

mkdir -p "$skills_dir"
installed_any="false"

# Sub-agents are copied, not linked: ~/.claude/agents is a folder users keep their own agents in,
# and a copy is a plain file every host loads, which a link into the skill folder is not
# guaranteed to be. A file already there is compared by content: identical is left alone,
# different is kept and reported (replaced, with a copy kept, only under --force-agents).
install_agents() {
  local src_dir="$source_root/skills/orch/agents" f name dest backup
  [[ -d "$src_dir" ]] || { echo "Claude agents: none in source"; return 0; }
  for f in "$src_dir"/*.md; do
    name="$(basename "$f")"
    dest="$home_dir/.claude/agents/$name"
    mkdir -p "$home_dir/.claude/agents"
    if [[ ! -e "$dest" && ! -L "$dest" ]]; then
      cp "$f" "$dest"
      echo "Installed agent ${name%.md} -> $dest"
    elif [[ -f "$dest" ]] && cmp -s "$f" "$dest"; then
      echo "Agent ${name%.md} already current: $dest"
    elif [[ "$force_agents" == "true" ]]; then
      backup="$home_dir/.agents/agent-${name%.md}-backup-$(date +%Y%m%d-%H%M%S).md"
      cp "$dest" "$backup" 2>/dev/null || : > "$backup"
      rm -f "$dest"
      cp "$f" "$dest"
      echo "Replaced agent ${name%.md} at $dest (previous kept at $backup)"
    else
      echo "Kept your different agent ${name%.md} at $dest (not overwritten; --force-agents replaces it)"
    fi
  done
}

for src in "$source_root"/skills/*/; do
  [[ "$agents_only" == "true" || "$wire_only" == "true" ]] && break
  name="$(basename "$src")"
  wanted "$name" || continue
  [[ -f "$src/SKILL.md" ]] || die "skills/$name has no SKILL.md"
  version="$(read_version "$src")"
  dest="$skills_dir/$name"
  if [[ -e "$dest" || -L "$dest" ]]; then
    [[ "$force" == "true" ]] || die "install already exists at $dest; use --force to replace it, or bootstrap.sh update"
    backup="$home_dir/.agents/$name-backup-$(date +%Y%m%d-%H%M%S).tgz"
    tar -czf "$backup" -C "$skills_dir" "$name"
    rm -rf "$dest"
    echo "Backed up previous $name to $backup"
  fi
  tmp="$(mktemp -d)"
  cp -R "$src" "$tmp/$name"
  find "$tmp/$name" -name __pycache__ -type d -prune -exec rm -rf {} +
  find "$tmp/$name" -name .DS_Store -delete
  mv "$tmp/$name" "$dest"
  rmdir "$tmp"
  echo "Installed $name $version -> $dest"
  installed_any="true"
  if [[ "$claude_link" == "true" ]]; then
    link="$home_dir/.claude/skills/$name"
    target="../../.agents/skills/$name"
    mkdir -p "$home_dir/.claude/skills"
    if [[ -L "$link" ]] && [[ "$(readlink "$link")" == "$target" ]]; then
      echo "Claude skill link already current: $link"
    elif [[ -e "$link" || -L "$link" ]]; then
      echo "Kept your existing Claude skill path: $link (not overwritten)"
    else
      ln -s "$target" "$link"
      echo "Claude skill link: $link -> $target"
    fi
  fi
done

[[ "$installed_any" == "true" || "$agents_only" == "true" || "$wire_only" == "true" ]] || die "nothing matched --only"

if [[ "$wire_only" == "true" ]]; then
  :
elif [[ "$claude_link" == "true" ]] && wanted orch; then
  install_agents
else
  echo "Claude agents: skipped"
fi

[[ "$agents_only" == "true" ]] && exit 0

if [[ "$claude_link" == "true" ]] && wanted orch && [[ -d "$skills_dir/orch/commands" ]]; then
  link="$home_dir/.claude/commands/orch"
  mkdir -p "$(dirname "$link")"
  if [[ -e "$link" && ! -L "$link" ]]; then
    die "$link exists and is not a symlink; move it aside first"
  fi
  rm -f "$link"
  ln -s "../../.agents/skills/orch/commands" "$link"
  echo "Claude commands link: $link -> ../../.agents/skills/orch/commands"
else
  echo "Claude commands link: skipped"
fi

if wanted orch; then
  retire_session_close
  wire_hosts
else
  echo "Retirement and host wiring: skipped (orch not selected)"
fi
