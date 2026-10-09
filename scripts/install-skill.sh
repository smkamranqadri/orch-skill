#!/usr/bin/env bash
# Install the skills in this repo (skills/*) into a user's home: ~/.agents/skills/<name>,
# plus Claude discovery links ~/.claude/skills/<name>, the command link ~/.claude/commands/orch,
# and orch's four named sub-agent
# definitions ~/.claude/agents/<name>.md (copied, never overwritten). Run from a source clone only.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-skill.sh --source <repo-root> [--home <dir>] [--force] [--force-agents] [--no-claude-link] [--agents-only] [--only <name>]

Options:
  --source <path>    Source repo root containing skills/<name>/SKILL.md. Also ORCH_SKILL_SOURCE.
  --home <dir>       Home directory to install into. Defaults to $HOME.
  --force            Replace an existing ~/.agents/skills/<name> (a .tgz backup is kept).
  --force-agents     Replace a different ~/.claude/agents/<name>.md (copy kept in ~/.agents/).
                     Without it a different file is kept and reported, never overwritten.
  --no-claude-link   Skip ~/.claude/skills links, commands link and agent definitions.
  --agents-only      Install only the sub-agent definitions; leave the skills alone.
  --only <name>      Install only this skill (orch or session-close). Repeatable.
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
only=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source) [[ $# -ge 2 ]] || die "--source requires a path"; source_arg="$2"; shift 2 ;;
    --home) [[ $# -ge 2 ]] || die "--home requires a path"; home_dir="$2"; shift 2 ;;
    --force) force="true"; shift ;;
    --force-agents) force_agents="true"; shift ;;
    --agents-only) agents_only="true"; shift ;;
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
  [[ "$agents_only" == "true" ]] && break
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

[[ "$installed_any" == "true" || "$agents_only" == "true" ]] || die "nothing matched --only"

if [[ "$claude_link" == "true" ]] && wanted orch; then
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
