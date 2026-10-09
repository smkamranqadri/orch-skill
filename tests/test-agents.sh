#!/usr/bin/env bash
# Sub-agent install tests in a temporary HOME. Never touches the real ~/.agents or ~/.claude.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
log="$tmp/log"
names="worker explorer researcher designer"
b="$repo_root/bootstrap.sh"

fail() { echo "FAIL: $*" >&2; echo "--- last output ---" >&2; cat "$log" >&2 || true; exit 1; }
mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"; }

# 0. the source ships exactly the four, each with a matching name in its frontmatter
test "$(ls "$repo_root/skills/orch/agents" | wc -l | tr -d ' ')" = 4 || fail "source should ship exactly four agents"
for n in $names; do
  grep -q "^name: $n\$" "$repo_root/skills/orch/agents/$n.md" || fail "$n.md frontmatter name mismatch"
done

# 1. fresh install creates the four as plain files identical to the source
home="$tmp/home1"; mkdir -p "$home"
"$b" install --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "install failed"
for n in $names; do
  test -f "$home/.claude/agents/$n.md" || fail "$n not installed"
  test ! -L "$home/.claude/agents/$n.md" || fail "$n should be a copy, not a link"
  cmp -s "$repo_root/skills/orch/agents/$n.md" "$home/.claude/agents/$n.md" || fail "$n differs from source"
  grep -q "Installed agent $n " "$log" || fail "install did not report $n"
done
"$b" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "check should pass when agents are current"
grep -q "Agent already current: worker" "$log" || fail "check did not report agents current"
rm "$home/.claude/agents/researcher.md"
if "$b" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1; then fail "check should exit 1 on a missing agent"; fi
grep -q "Agent not installed: researcher" "$log" || fail "check did not report the missing agent"

# 2. identical existing files are left alone (mtime unchanged)
home="$tmp/home2"; mkdir -p "$home/.claude/agents"
cp "$repo_root/skills/orch/agents/worker.md" "$home/.claude/agents/worker.md"
touch -t 202001010000 "$home/.claude/agents/worker.md"
before="$(mtime "$home/.claude/agents/worker.md")"
"$b" install --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "install with identical agent failed"
after="$(mtime "$home/.claude/agents/worker.md")"
test "$before" = "$after" || fail "identical agent was rewritten"
grep -q "Agent worker already current" "$log" || fail "identical agent not reported current"
test -f "$home/.claude/agents/explorer.md" || fail "other agents should still be installed"

# 3. a different existing file is not clobbered, and is reported
home="$tmp/home3"; mkdir -p "$home/.claude/agents"
echo "my own worker" > "$home/.claude/agents/worker.md"
"$b" install --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "install with different agent should still exit 0"
test "$(cat "$home/.claude/agents/worker.md")" = "my own worker" || fail "different agent was overwritten"
grep -q "Kept your different agent worker" "$log" || fail "kept file not reported"
test -f "$home/.claude/agents/designer.md" || fail "other agents should still be installed"
if "$b" check --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1; then fail "check should exit 1 on a different agent"; fi
grep -q "Agent differs: worker" "$log" || fail "check did not report the different agent"
#    update keeps it too, and installs a missing one
rm "$home/.claude/agents/explorer.md"
"$b" update --source "$repo_root" --home "$home" --no-herdr >"$log" 2>&1 || fail "update failed"
test "$(cat "$home/.claude/agents/worker.md")" = "my own worker" || fail "update overwrote a different agent"
test -f "$home/.claude/agents/explorer.md" || fail "update did not restore a missing agent"
#    --force replaces it and keeps a copy
"$b" install --source "$repo_root" --home "$home" --no-herdr --force >"$log" 2>&1 || fail "install --force failed"
cmp -s "$repo_root/skills/orch/agents/worker.md" "$home/.claude/agents/worker.md" || fail "--force did not replace the agent"
grep -q "my own worker" "$home"/.agents/agent-worker-backup-*.md || fail "--force kept no copy of the old agent"

# 4. the opt-out skips them, and so does installing only the other skill
home="$tmp/home4"; mkdir -p "$home"
"$b" install --source "$repo_root" --home "$home" --no-herdr --no-claude-link >"$log" 2>&1 || fail "install --no-claude-link failed"
test ! -e "$home/.claude/agents" || fail "--no-claude-link should skip the agents"
home="$tmp/home5"; mkdir -p "$home"
"$b" install --source "$repo_root" --home "$home" --no-herdr --only session-close >"$log" 2>&1 || fail "install --only session-close failed"
test ! -e "$home/.claude/agents" || fail "--only session-close should skip the agents"

echo "agent tests: pass"
