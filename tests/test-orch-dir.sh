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

# 3. a ../<repo>.reports/orch run beside the repo is ignored; --check creates nothing
mkdir -p "$tmp/old" && git -C "$tmp/old" init -q
mkdir -p "$tmp/old.reports/orch" && echo "# ledger" > "$tmp/old.reports/orch/ledger.md"
out="$("$S" --check "$tmp/old")"
[[ "$out" == "$tmp/old/.orch" ]] || fail "--check used a ../old.reports run: $out"
test ! -e "$tmp/old/.orch" || fail "--check created .orch"
out="$("$S" "$tmp/old")"
[[ "$out" == "$tmp/old/.orch" ]] || fail "use followed a ../old.reports run: $out"
test -d "$tmp/old/.orch" || fail ".orch not created beside a ../old.reports run"
grep -qxF '.orch/' "$tmp/old/.git/info/exclude" || fail "exclude entry missing"
test -f "$tmp/old.reports/orch/ledger.md" || fail "old.reports run was touched"

# 4. unknown flags fail clearly instead of being taken as a path
for flag in --migrate --bogus; do
  if err="$("$S" "$flag" "$tmp/old" 2>&1 >/dev/null)"; then fail "$flag should fail"; fi
  [[ "$err" == "Error: unknown option: $flag"* ]] || fail "$flag message: $err"
done

# 4b. an unknown flag after the path, or a second path, fails too
if err="$("$S" "$tmp/old" --migrate 2>&1 >/dev/null)"; then fail "path then --migrate should fail"; fi
[[ "$err" == "Error: unknown option: --migrate"* ]] || fail "path then --migrate message: $err"
if err="$("$S" --check --bogus 2>&1 >/dev/null)"; then fail "--check --bogus should fail"; fi
[[ "$err" == "Error: unknown option: --bogus"* ]] || fail "--check --bogus message: $err"
if err="$("$S" "$tmp/old" "$tmp/proj" 2>&1 >/dev/null)"; then fail "two paths should fail"; fi
[[ "$err" == "Error: more than one path"* ]] || fail "two paths message: $err"

# 4c. paths with spaces: repo and linked worktree both resolve the main checkout's .orch
mkdir -p "$tmp/my repo" && git -C "$tmp/my repo" init -q
git -C "$tmp/my repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
git -C "$tmp/my repo" worktree add -q "$tmp/my repo.wt/feat x" -b featx
[[ "$("$S" "$tmp/my repo")" == "$tmp/my repo/.orch" ]] || fail "spaces: repo dir"
[[ "$("$S" "$tmp/my repo.wt/feat x")" == "$tmp/my repo/.orch" ]] || fail "spaces: worktree dir"
[[ "$(cd "$tmp/my repo.wt/feat x" && "$S")" == "$tmp/my repo/.orch" ]] || fail "spaces: worktree cwd"
test ! -e "$tmp/my repo.wt/feat x/.orch" || fail "spaces: worktree got its own .orch"
[[ "$(grep -cxF '.orch/' "$tmp/my repo/.git/info/exclude")" == "1" ]] || fail "spaces: exclude entry count"

# 5. not a git repo: .orch under the path, no exclude needed
mkdir -p "$tmp/plain"
[[ "$("$S" "$tmp/plain")" == "$tmp/plain/.orch" ]] || fail "plain dir"
test -d "$tmp/plain/.orch" || fail "plain .orch not created"

echo "orch-dir tests: pass"
