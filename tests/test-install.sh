#!/usr/bin/env bash
# Installer tests in a temporary HOME. Never touches the real ~/.agents or ~/.claude.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
home="$tmp/home"
log="$tmp/log"
mkdir -p "$home"

fail() { echo "FAIL: $*" >&2; echo "--- last output ---" >&2; cat "$log" >&2 || true; exit 1; }

# 1. install (Herdr check skipped here; tested on its own below)
"$repo_root/bootstrap.sh" install --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "install exited non-zero"
grep -q "Installed orch " "$log" || fail "install did not report orch"
grep -q "Installed session-close " "$log" || fail "install did not report session-close"
test -f "$home/.agents/skills/orch/SKILL.md" || fail "orch SKILL.md missing"
test -f "$home/.agents/skills/orch/scripts/orch-watch.py" || fail "watcher missing"
test -f "$home/.agents/skills/session-close/SKILL.md" || fail "session-close SKILL.md missing"
test -L "$home/.claude/commands/orch" || fail "commands link missing"
test -f "$home/.claude/commands/orch/start.md" || fail "commands link does not resolve"
test ! -e "$home/.agents/skills/orch/research" || fail "research must not be installed"

# 2. byte-identical to source
diff -r --exclude=__pycache__ --exclude=.DS_Store "$repo_root/skills/orch" "$home/.agents/skills/orch" >"$log" 2>&1 || fail "installed orch differs from source"
diff -r --exclude=__pycache__ --exclude=.DS_Store "$repo_root/skills/session-close" "$home/.agents/skills/session-close" >"$log" 2>&1 || fail "installed session-close differs from source"

# 3. second install refuses without --force
if "$repo_root/bootstrap.sh" install --source "$repo_root" --home "$home" >"$log" 2>&1; then fail "second install should refuse"; fi
grep -q "use --force" "$log" || fail "refusal message missing"

# 4. check says current
"$repo_root/bootstrap.sh" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "check should exit 0 when current"
grep -q "Already current: orch" "$log" || fail "check did not say orch current"
grep -q "Already current: session-close" "$log" || fail "check did not say session-close current"

# 5. drift is detected and update restores it, keeping a backup
echo "# drift" >> "$home/.agents/skills/orch/SKILL.md"
if "$repo_root/bootstrap.sh" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1; then fail "check should exit 1 on drift"; fi
grep -q "Update available: orch" "$log" || fail "drift not reported"
grep -q "Already current: session-close" "$log" || fail "untouched skill should stay current"
"$repo_root/bootstrap.sh" update --source "$repo_root" --home "$home" >"$log" 2>&1 || fail "update failed"
grep -q "Backed up previous orch" "$log" || fail "update did not back up"
grep -q "Installed orch " "$log" || fail "update did not reinstall orch"
ls "$home/.agents/"orch-backup-*.tgz >/dev/null 2>&1 || fail "backup tgz missing"
diff -r --exclude=__pycache__ "$repo_root/skills/orch" "$home/.agents/skills/orch" >"$log" 2>&1 || fail "update did not restore orch"
"$repo_root/bootstrap.sh" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "check should be current after update"

# 6. --only and --no-claude-link
home2="$tmp/home2"; mkdir -p "$home2"
"$repo_root/bootstrap.sh" install --source "$repo_root" --home "$home2" --only session-close --no-claude-link >"$log" 2>&1 || fail "only install failed"
test -f "$home2/.agents/skills/session-close/SKILL.md" || fail "only: session-close missing"
test ! -e "$home2/.agents/skills/orch" || fail "only: orch should not be installed"
test ! -e "$home2/.claude/commands/orch" || fail "no-claude-link: link should not exist"

# 7. a pre-existing non-symlink commands dir is refused, not overwritten
home3="$tmp/home3"; mkdir -p "$home3/.claude/commands/orch"
echo keep > "$home3/.claude/commands/orch/mine.md"
if "$repo_root/bootstrap.sh" install --source "$repo_root" --home "$home3" >"$log" 2>&1; then fail "should refuse to replace a real directory"; fi
test -f "$home3/.claude/commands/orch/mine.md" || fail "real directory was destroyed"

# 8. Herdr doctor: a temp HOME has no Herdr skill, so doctor exits 1 and names the fix;
#    with --with-herdr and the binary present it writes the skill from `herdr --skill`.
if "$repo_root/bootstrap.sh" doctor --home "$home" >"$log" 2>&1; then fail "doctor should exit 1 without the Herdr skill"; fi
grep -q "Herdr skill: missing" "$log" || fail "doctor did not report the missing skill"
grep -q "npx skills add herdrdev/herdr" "$log" || fail "doctor did not name the skill install"
if command -v herdr >/dev/null 2>&1; then
  "$repo_root/bootstrap.sh" doctor --home "$home" --with-herdr >"$log" 2>&1 || fail "doctor --with-herdr failed"
  test -s "$home/.agents/skills/herdr/SKILL.md" || fail "with-herdr did not write the skill"
  grep -q "^name: herdr" "$home/.agents/skills/herdr/SKILL.md" || fail "written skill is not the herdr skill"
  "$repo_root/bootstrap.sh" doctor --home "$home" >"$log" 2>&1 || fail "doctor should pass after with-herdr"
  echo "# stale" >> "$home/.agents/skills/herdr/SKILL.md"
  if "$repo_root/bootstrap.sh" doctor --home "$home" >"$log" 2>&1; then fail "doctor should exit 1 on a stale Herdr skill"; fi
  grep -q "Herdr skill: STALE" "$log" || fail "doctor did not report stale"
  "$repo_root/bootstrap.sh" doctor --home "$home" --with-herdr >"$log" 2>&1 || fail "with-herdr should refresh a stale skill"
  grep -q "refreshed" "$log" || fail "refresh not reported"
  "$repo_root/bootstrap.sh" doctor --home "$home" >"$log" 2>&1 || fail "doctor should pass after refresh"
else
  echo "(herdr binary absent on this machine: with-herdr path not exercised)"
fi
# install without --no-herdr prints the Herdr check and still exits 0
"$repo_root/bootstrap.sh" install --source "$repo_root" --home "$home" --force >"$log" 2>&1 || fail "install with Herdr check exited non-zero"
grep -q "Herdr binary:" "$log" || fail "install did not run the Herdr check"

echo "install tests: pass"
