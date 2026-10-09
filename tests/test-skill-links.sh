#!/usr/bin/env bash
# Claude discovery links, exercised only in temporary homes.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
log="$tmp/log"
fail() { echo "FAIL: $*" >&2; cat "$log" >&2; exit 1; }
install() {
  "$repo_root/bootstrap.sh" install --source "$repo_root" --home "$1" --no-herdr "${@:2}" >"$log" 2>&1 || fail "install $1"
}
check() {
  "$repo_root/bootstrap.sh" check --source "$repo_root" --home "$1" --no-herdr "${@:2}" >"$log" 2>&1
}

home="$tmp/fresh"
install "$home"
for name in orch session-close; do
  link="$home/.claude/skills/$name"
  test -L "$link" || fail "fresh $name link missing"
  [[ "$(readlink "$link")" == "../../.agents/skills/$name" ]] || fail "wrong $name link target"
  test -f "$link/SKILL.md" || fail "$name link does not resolve"
done
check "$home" || fail "fresh links should check current"
# An existing correct symlink must retain its inode and timestamp, even on a forced install.
python3 -I -c 'import os,sys; s=os.lstat(sys.argv[1]); print(s.st_ino,s.st_mtime_ns)' "$home/.claude/skills/orch" > "$tmp/before"
install "$home" --force
python3 -I -c 'import os,sys; s=os.lstat(sys.argv[1]); print(s.st_ino,s.st_mtime_ns)' "$home/.claude/skills/orch" > "$tmp/after"
cmp -s "$tmp/before" "$tmp/after" || fail "correct link was recreated"
grep -q 'Claude skill link already current:' "$log" || fail "correct link not reported"

# Check must detect a missing link while the installed skill itself is current.
unlink "$home/.claude/skills/session-close"
if check "$home"; then fail "missing link should fail check"; fi
grep -q 'Claude skill link missing: session-close' "$log" || fail "missing link not reported"
check "$home" --no-claude-link || fail "opt-out check should ignore missing links"

for kind in file directory foreign-link dangling-link; do
  home="$tmp/$kind"
  mkdir -p "$home/.claude/skills" "$home/other"
  echo keep > "$home/other/marker"
  link="$home/.claude/skills/orch"
  case "$kind" in
    file) echo keep > "$link" ;;
    directory) mkdir "$link"; echo keep > "$link/marker" ;;
    foreign-link) ln -s "$home/other" "$link" ;;
    dangling-link) ln -s "$home/absent" "$link" ;;
  esac
  install "$home" --force
  grep -q 'Kept your existing Claude skill path:' "$log" || fail "$kind not reported"
  case "$kind" in
    file) [[ "$(cat "$link")" == keep ]] || fail "foreign file changed" ;;
    directory) [[ "$(cat "$link/marker")" == keep ]] || fail "foreign directory changed" ;;
    foreign-link) [[ "$(readlink "$link")" == "$home/other" ]] || fail "foreign link changed" ;;
    dangling-link) [[ "$(readlink "$link")" == "$home/absent" ]] || fail "dangling link changed" ;;
  esac
  if check "$home"; then fail "$kind should fail check"; fi
  grep -q 'Claude skill link differs: orch' "$log" || fail "$kind check not reported"
done

home="$tmp/opt-out"
install "$home" --no-claude-link
test ! -e "$home/.claude/skills" || fail "opt-out created skill links"
check "$home" --no-claude-link || fail "opt-out check"
home="$tmp/only"
install "$home" --only session-close
test -L "$home/.claude/skills/session-close" || fail "only: selected link missing"
test ! -e "$home/.claude/skills/orch" || fail "only: unselected link created"
check "$home" --only session-close || fail "only: check failed"
echo "skill-link tests: pass"
