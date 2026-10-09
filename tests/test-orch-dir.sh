#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$repo_root/skills/orch/scripts/orch-dir.sh"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# 1. fresh git repo: .orch created and excluded, nothing to commit
mkdir -p "$tmp/proj" && git -C "$tmp/proj" init -q
out="$("$S" "$tmp/proj")"
[[ "$out" == "$tmp/proj/.orch" ]] || fail "dir: $out"
test -d "$tmp/proj/.orch" || fail ".orch not created"
grep -qxF '.orch/' "$tmp/proj/.git/info/exclude" || fail "exclude entry missing"
touch "$tmp/proj/.orch/ledger.md"
[[ -z "$(git -C "$tmp/proj" status --short)" ]] || fail ".orch shows in git status"
"$S" "$tmp/proj" >/dev/null
[[ "$(grep -cxF '.orch/' "$tmp/proj/.git/info/exclude")" == "1" ]] || fail "exclude entry duplicated"

# 2. from inside a worktree, the dir is the main checkout's .orch and the exclude is shared
git -C "$tmp/proj" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$tmp/proj" worktree add -q "$tmp/proj.wt/feat" -b feat
out="$("$S" "$tmp/proj.wt/feat")"
[[ "$out" == "$tmp/proj/.orch" ]] || fail "worktree must resolve to the main checkout's .orch, got: $out"
test ! -e "$tmp/proj.wt/feat/.orch" || fail "worktree got its own .orch"
mkdir -p "$tmp/proj.wt/feat/.orch" && touch "$tmp/proj.wt/feat/.orch/x"
[[ -z "$(git -C "$tmp/proj.wt/feat" status --short)" ]] || fail ".orch visible in worktree git status (exclude not shared)"

# 3. legacy run wins while it exists; --check creates nothing
mkdir -p "$tmp/old" && git -C "$tmp/old" init -q
mkdir -p "$tmp/old.reports/orch" "$tmp/old.reports/agent-a" && echo "# ledger" > "$tmp/old.reports/orch/ledger.md" && echo brief > "$tmp/old.reports/agent-a/brief-x.md"
out="$("$S" --check "$tmp/old" 2>/dev/null)"
[[ "$out" == "$tmp/old.reports/orch" ]] || fail "legacy not detected by --check: $out"
test ! -e "$tmp/old/.orch" || fail "--check created .orch"
out="$("$S" "$tmp/old" 2>/dev/null)"
[[ "$out" == "$tmp/old.reports/orch" ]] || fail "legacy not used: $out"
test ! -e "$tmp/old/.orch" || fail "use created .orch beside a legacy run"

# 4. migrate moves ledger and agent folders, then the new dir is used
out="$("$S" --migrate "$tmp/old" 2>/dev/null)"
[[ "$out" == "$tmp/old/.orch" ]] || fail "migrate dir: $out"
test -f "$tmp/old/.orch/ledger.md" || fail "ledger not moved"
test -f "$tmp/old/.orch/agent-a/brief-x.md" || fail "agent folder not moved"
test ! -e "$tmp/old.reports" || fail "legacy parent not removed"
grep -qxF '.orch/' "$tmp/old/.git/info/exclude" || fail "exclude after migrate"
[[ "$("$S" "$tmp/old")" == "$tmp/old/.orch" ]] || fail "new dir not used after migrate"
if "$S" --migrate "$tmp/old" >/dev/null 2>&1; then fail "second migrate should fail"; fi

# 5. not a git repo: .orch under the path, no exclude needed
mkdir -p "$tmp/plain"
[[ "$("$S" "$tmp/plain")" == "$tmp/plain/.orch" ]] || fail "plain dir"
test -d "$tmp/plain/.orch" || fail "plain .orch not created"

echo "orch-dir tests: pass"
