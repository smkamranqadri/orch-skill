#!/usr/bin/env bash
# Host wiring (Codex, Command Code, agy) and the session-close retirement, in temporary homes.
# Never touches the real ~/.agents, ~/.claude, ~/.codex, ~/.commandcode or ~/.gemini.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
log="$tmp/log"
b="$repo_root/bootstrap.sh"
fx="$repo_root/tests/fixtures/session-close"

fail() { echo "FAIL: $*" >&2; echo "--- last output ---" >&2; cat "$log" >&2 || true; exit 1; }
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"; }
run() { "$b" "$@" --no-herdr >"$log" 2>&1; }
has() { grep -q -x -F -- "$1" "$log" || fail "missing line: $1"; }
hasnt() { if grep -q -x -F -- "$1" "$log"; then fail "unexpected line: $1"; fi; }

# An old install: session-close package <ver>, its Claude link, an orch package.
old_home() {  # <home> <session-close version>
  local h="$1" v="$2"
  mkdir -p "$h/.agents/skills/session-close" "$h/.claude/skills"
  cp "$fx/SKILL-$v.md" "$h/.agents/skills/session-close/SKILL.md"
  ln -s ../../.agents/skills/session-close "$h/.claude/skills/session-close"
}

cmds="$(cd "$repo_root/skills/orch/commands" && ls *.md)"
test -f "$repo_root/skills/orch/commands/close.md" || fail "source has no orch close command"
test -f "$repo_root/skills/orch/commands/start.md" || fail "source has no orch start command"

# 1. a fresh install wires every host; each copy is byte-identical to the source command
home="$tmp/h1"
run install --source "$repo_root" --home "$home" --hosts all || fail "install --hosts all failed"
for c in $cmds; do
  cmp -s "$repo_root/skills/orch/commands/$c" "$home/.codex/prompts/orch-$c" || fail "codex prompt orch-$c differs"
  cmp -s "$repo_root/skills/orch/commands/$c" "$home/.commandcode/commands/orch-$c" || fail "cmd command orch-$c differs"
  test ! -L "$home/.codex/prompts/orch-$c" || fail "codex prompt should be a copy"
done
[[ "$(readlink "$home/.gemini/config/skills/orch")" == "../../../.agents/skills/orch" ]] || fail "agy link target"
test -f "$home/.gemini/config/skills/orch/commands/close.md" || fail "agy link does not resolve to orch close"
test -f "$home/.claude/commands/orch/close.md" || fail "claude commands link does not reach close"
grep -q -x -F "Codex usage: /prompts:orch-start /prompts:orch-close (custom prompts are deprecated upstream; the orch skill in ~/.agents/skills also loads by name)" "$log" || fail "codex usage line"
grep -q -x -F "Command Code usage: /orch-start /orch-close" "$log" || fail "cmd usage line"
grep -q -F 'agy usage: no custom slash commands; say "run the orch start step"' "$log" || fail "agy usage line"
run check --source "$repo_root" --home "$home" --hosts all || fail "check should pass on a fresh wired install"
has "Codex prompt already current: $home/.codex/prompts/orch-start.md"
has "Codex prompt already current: $home/.codex/prompts/orch-close.md"
has "Command Code command already current: $home/.commandcode/commands/orch-start.md"
has "Command Code command already current: $home/.commandcode/commands/orch-close.md"
has "agy skill link already current: $home/.gemini/config/skills/orch"
n="$(grep -c '^Codex prompt already current: ' "$log")"
[[ "$n" == "$(echo "$cmds" | wc -l | tr -d ' ')" ]] || fail "check reported $n codex prompts, expected one per command"

# 2. check names each broken host item; update repairs them
rm "$home/.codex/prompts/orch-close.md"
echo "# drift" >> "$home/.commandcode/commands/orch-start.md"
unlink "$home/.gemini/config/skills/orch"
if run check --source "$repo_root" --home "$home" --hosts all; then fail "check should exit 1 on broken wiring"; fi
has "Codex prompt missing: $home/.codex/prompts/orch-close.md"
has "Command Code command differs: $home/.commandcode/commands/orch-start.md (not shipped by orch; kept; install --force replaces it)"
has "agy skill link missing: $home/.gemini/config/skills/orch"
has "Codex prompt already current: $home/.codex/prompts/orch-start.md"
run update --source "$repo_root" --home "$home" --hosts all || fail "update failed"
test -f "$home/.codex/prompts/orch-close.md" -a -L "$home/.gemini/config/skills/orch" || fail "update did not repair the missing items"
# the drifted copy was edited, so it is the user's: update keeps it, install --force replaces it
grep -q -x '# drift' "$home/.commandcode/commands/orch-start.md" || fail "update overwrote an edited prompt"
if run check --source "$repo_root" --home "$home" --hosts all; then fail "check should still flag the edited prompt"; fi
has "Command Code command differs: $home/.commandcode/commands/orch-start.md (not shipped by orch; kept; install --force replaces it)"
run install --source "$repo_root" --home "$home" --hosts all --force || fail "install --force over an edited prompt"
cmp -s "$repo_root/skills/orch/commands/start.md" "$home/.commandcode/commands/orch-start.md" || fail "--force did not restore the cmd command"
grep -l -x '# drift' "$home"/.agents/orch-prompt-backups/*/* >/dev/null 2>&1 || fail "--force kept no copy of the edited prompt"
run check --source "$repo_root" --home "$home" --hosts all || fail "check should pass after update and --force repaired the wiring"

# 3. a second install is idempotent: identical copies are not rewritten, the link keeps its inode
touch -t 202001010000 "$home/.codex/prompts/orch-start.md"
before="$(mtime "$home/.codex/prompts/orch-start.md")"
ino="$(ls -di "$home/.gemini/config/skills/orch" | cut -d" " -f1)"
run install --source "$repo_root" --home "$home" --hosts all --force || fail "re-install failed"
[[ "$(mtime "$home/.codex/prompts/orch-start.md")" == "$before" ]] || fail "identical codex prompt was rewritten"
[[ "$(ls -di "$home/.gemini/config/skills/orch" | cut -d" " -f1)" == "$ino" ]] || fail "agy link was recreated"
has "Codex prompt already current: $home/.codex/prompts/orch-start.md"
has "agy skill link already current: $home/.gemini/config/skills/orch"
run check --source "$repo_root" --home "$home" --hosts all || fail "check after re-install"

# 4. foreign content at a wired path is kept, reported, and never overwritten
home="$tmp/h4"; mkdir -p "$home/.gemini/config/skills" "$home/.commandcode/commands" "$home/other"
echo keep > "$home/other/marker"
ln -s "$home/other" "$home/.gemini/config/skills/orch"
mkdir "$home/.commandcode/commands/orch-start.md"
run install --source "$repo_root" --home "$home" --hosts all || fail "install over foreign paths failed"
has "Kept your existing agy skill path: $home/.gemini/config/skills/orch (not overwritten)"
has "Kept your existing Command Code command path: $home/.commandcode/commands/orch-start.md (not a plain file; not overwritten)"
[[ "$(readlink "$home/.gemini/config/skills/orch")" == "$home/other" ]] || fail "foreign agy link changed"
test -d "$home/.commandcode/commands/orch-start.md" || fail "foreign directory replaced"
if run check --source "$repo_root" --home "$home" --hosts all; then fail "check should flag foreign wired paths"; fi
has "agy skill link differs: $home/.gemini/config/skills/orch (existing path kept)"

# 5. hosts: none skips them, a list picks them, auto follows the folders
home="$tmp/h5"
run install --source "$repo_root" --home "$home" --hosts none || fail "hosts none"
test ! -e "$home/.codex" -a ! -e "$home/.commandcode" -a ! -e "$home/.gemini" || fail "hosts none wrote a host folder"
run check --source "$repo_root" --home "$home" --hosts none || fail "check with hosts none"
hasnt "agy skill link missing: $home/.gemini/config/skills/orch"
home="$tmp/h5b"
run install --source "$repo_root" --home "$home" --hosts codex,agy || fail "hosts list"
test -f "$home/.codex/prompts/orch-start.md" -a -L "$home/.gemini/config/skills/orch" || fail "hosts list missed a host"
test ! -e "$home/.commandcode" || fail "hosts list wired cmd"
home="$tmp/h5c"; mkdir -p "$home/.codex"
run install --source "$repo_root" --home "$home" || fail "hosts auto"
test -f "$home/.codex/prompts/orch-start.md" || fail "auto skipped a host whose folder exists"
if command -v cmd >/dev/null 2>&1; then test -f "$home/.commandcode/commands/orch-start.md" || fail "auto skipped cmd on PATH"
else test ! -e "$home/.commandcode" || fail "auto wired cmd that is not installed"; fi
if command -v agy >/dev/null 2>&1; then test -L "$home/.gemini/config/skills/orch" || fail "auto skipped agy on PATH"
else test ! -e "$home/.gemini" || fail "auto wired agy that is not installed"; fi

# 6. upgrade from the 0.10.0 / 1.0.2 install: session-close is gone, orch is current
home="$tmp/h6"
"$b" install --source "$repo_root" --home "$home" --only orch --no-herdr --hosts none >/dev/null 2>&1 || fail "stage old orch"
old_home "$home" 1.0.2
# Stand-in for the 0.10.0 package: the shipped tree with the old text. Any difference from the
# new source makes the package "differs", which is all the upgrade needs.
echo "# orch 0.10.0" >> "$home/.agents/skills/orch/SKILL.md"
if run check --source "$repo_root" --home "$home" --hosts all; then fail "old install should not check current"; fi
has "Update available: orch (installed copy differs from source)"
has "session-close leftover: link $home/.claude/skills/session-close (update removes it)"
has "session-close leftover: package $home/.agents/skills/session-close (update removes it)"
run update --source "$repo_root" --home "$home" --hosts all || fail "upgrade update failed"
has "Retired session-close link: $home/.claude/skills/session-close"
has "Retired session-close package: $home/.agents/skills/session-close"
test ! -e "$home/.claude/skills/session-close" -a ! -L "$home/.claude/skills/session-close" || fail "session-close link remains"
test ! -e "$home/.agents/skills/session-close" || fail "session-close package remains"
run check --source "$repo_root" --home "$home" --hosts all || fail "check should pass after the upgrade"
has "Already current: orch"
diff -r --exclude=__pycache__ "$repo_root/skills/orch" "$home/.agents/skills/orch" >"$log" 2>&1 || fail "orch not current after upgrade"
run update --source "$repo_root" --home "$home" --hosts all || fail "second update"
hasnt "Retired session-close package: $home/.agents/skills/session-close"

# 6b. update alone removes a leftover when orch itself is already current
old_home "$home" 1.0.2
if run check --source "$repo_root" --home "$home" --hosts all; then fail "leftover with a current orch should fail check"; fi
has "Already current: orch"
has "session-close leftover: package $home/.agents/skills/session-close (update removes it)"
run update --source "$repo_root" --home "$home" --hosts all || fail "update with a current orch"
has "Retired session-close package: $home/.agents/skills/session-close"
test ! -e "$home/.agents/skills/session-close" -a ! -L "$home/.claude/skills/session-close" || fail "leftover remains after update"

# 7. handoff and close work with session-close gone: they name no retired or lore step, and every
#    installed path they cite exists in the upgraded home
for f in handoff close; do
  doc="$home/.agents/skills/orch/commands/$f.md"
  if grep -n -E 'session-close|/lore:|lore:retro|lore:load|core rule|preference [0-9]|coordination rule|(^|[^a-z])rule [0-9]' "$doc" >"$log"; then fail "$f.md cites a retired step or a rule number"; fi
  for ref in $(grep -o -E '~/\.agents/skills/[A-Za-z0-9_./-]*[A-Za-z0-9_]' "$doc" | sort -u); do
    test -e "$home/${ref#\~/}" || fail "$f.md cites $ref, which the upgraded install lacks"
  done
done
grep -q 'commands/close.md' "$home/.agents/skills/orch/commands/handoff.md" || fail "handoff does not point at orch close"
# close carries the decisions it took over from session-close and the plan: stamp via the helper,
# Run pointer removal, decisions to Intent, no forced worktree removal, commit only as rules allow
close="$home/.agents/skills/orch/commands/close.md"
grep -q -F '.agents/skills/kis/scripts/state-stamp.sh <project root>' "$close" || fail "close does not write the stamp through the helper"
grep -q -F 'delete the `Run:` line' "$close" || fail "close does not remove the Run pointer"
grep -q -F 'into the plan in `kis/intent/`' "$close" || fail "close does not flush decisions to Intent"
grep -q -F 'Never `git worktree remove --force`' "$close" || fail "close allows forced worktree removal"
grep -q -F 'a rule against committing wins' "$close" || fail "close does not defer to a no-commit rule"
if grep -q -i 'retro' "$close"; then fail "close still runs a retro"; fi
grep -q -F '.agents/skills/kis/scripts/state-stamp.sh' "$home/.agents/skills/orch/commands/handoff.md" || fail "handoff does not write the stamp"

# 8. every shipped session-close version is recognised; modified or foreign content is kept
for v in 1.0.0 1.0.1 1.0.2; do
  home="$tmp/h8-$v"; old_home "$home" "$v"
  run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install over $v"
  has "Retired session-close package: $home/.agents/skills/session-close"
  test ! -e "$home/.agents/skills/session-close" || fail "$v package remains"
done
home="$tmp/h8m"; old_home "$home" 1.0.2
echo "# my edit" >> "$home/.agents/skills/session-close/SKILL.md"
run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install over modified package"
has "Retired session-close link: $home/.claude/skills/session-close"
has "Kept $home/.agents/skills/session-close (modified or not shipped by orch; orch:close replaces it, remove it by hand)"
grep -q '^# my edit$' "$home/.agents/skills/session-close/SKILL.md" || fail "modified package was changed"
run check --source "$repo_root" --home "$home" --hosts none || fail "kept modified package must not fail check"
has "session-close kept (yours or modified): package $home/.agents/skills/session-close (orch:close replaces it; remove by hand)"
home="$tmp/h8x"; old_home "$home" 1.0.2
echo mine > "$home/.agents/skills/session-close/notes.md"
run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install over package with an extra file"
test -f "$home/.agents/skills/session-close/notes.md" -a -f "$home/.agents/skills/session-close/SKILL.md" || fail "package with an extra file was removed"
home="$tmp/h8l"; mkdir -p "$home/.claude/skills" "$home/other"
ln -s "$home/other" "$home/.claude/skills/session-close"
run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install over foreign link"
has "Kept $home/.claude/skills/session-close (not the link orch shipped for session-close; remove it by hand)"
[[ "$(readlink "$home/.claude/skills/session-close")" == "$home/other" ]] || fail "foreign session-close link changed"
home="$tmp/h8s"; mkdir -p "$home/.agents/skills" "$home/other"
cp "$fx/SKILL-1.0.2.md" "$home/other/SKILL.md"
ln -s "$home/other" "$home/.agents/skills/session-close"
run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install over symlinked package"
test -L "$home/.agents/skills/session-close" -a -f "$home/other/SKILL.md" || fail "symlinked package was removed"
home="$tmp/h8n"; old_home "$home" 1.0.2
run install --source "$repo_root" --home "$home" --only orch --no-claude-link --hosts none || fail "install --no-claude-link"
test -L "$home/.claude/skills/session-close" || fail "--no-claude-link must leave ~/.claude alone"

# 9. the agy retirement link goes too
home="$tmp/h9"; mkdir -p "$home/.gemini/config/skills"
ln -s ../../../.agents/skills/session-close "$home/.gemini/config/skills/session-close"
run install --source "$repo_root" --home "$home" --only orch --hosts none || fail "install with agy session-close link"
has "Retired session-close link: $home/.gemini/config/skills/session-close"
test ! -L "$home/.gemini/config/skills/session-close" || fail "agy session-close link remains"

# 10. the user's own prompt at a wired path is kept (install, update, check), never overwritten
home="$tmp/h10"; mkdir -p "$home/.codex/prompts" "$home/.commandcode/commands"
echo "my own prompt" > "$home/.codex/prompts/orch-start.md"
echo "my own command" > "$home/.commandcode/commands/orch-close.md"
run install --source "$repo_root" --home "$home" --hosts all || fail "install over the user's own prompts"
has "Kept your different Codex prompt: $home/.codex/prompts/orch-start.md (not shipped by orch; --force-prompts replaces it)"
has "Kept your different Command Code command: $home/.commandcode/commands/orch-close.md (not shipped by orch; --force-prompts replaces it)"
grep -q -x 'my own prompt' "$home/.codex/prompts/orch-start.md" || fail "install overwrote the user's codex prompt"
grep -q -x 'my own command' "$home/.commandcode/commands/orch-close.md" || fail "install overwrote the user's cmd command"
cmp -s "$repo_root/skills/orch/commands/status.md" "$home/.codex/prompts/orch-status.md" || fail "the other prompts were not installed"
rm "$home/.codex/prompts/orch-task.md"
run update --source "$repo_root" --home "$home" --hosts all || fail "update beside the user's prompts"
grep -q -x 'my own prompt' "$home/.codex/prompts/orch-start.md" || fail "update overwrote the user's codex prompt"
test -f "$home/.codex/prompts/orch-task.md" || fail "update did not restore the missing prompt"
test -z "$(ls "$home"/.agents/orch-prompt-backups/*/* 2>/dev/null)" || fail "a backup was made for a file that was kept"
inst() { "$repo_root/scripts/install-skill.sh" "$@" >"$log" 2>&1; }
inst --source "$repo_root" --home "$home" --hosts all --only orch --force || fail "install-skill --force"
grep -q -x 'my own prompt' "$home/.codex/prompts/orch-start.md" || fail "--force alone (skill replace) overwrote the user's prompt"
inst --source "$repo_root" --home "$home" --hosts all --force-prompts --wire-only || fail "install-skill --force-prompts"
cmp -s "$repo_root/skills/orch/commands/start.md" "$home/.codex/prompts/orch-start.md" || fail "--force-prompts did not replace the prompt"
grep -q -x 'my own prompt' "$home"/.agents/orch-prompt-backups/*/*orch-start.md || fail "--force-prompts kept no copy of the user's prompt"

# 11. a shipped older copy is replaced with a backup; a command dropped from the source takes its
#     shipped copy with it, and a user's orch-<name>.md with no source command is left alone
src="$tmp/src"; mkdir -p "$src"; cp -R "$repo_root/skills" "$repo_root/scripts" "$repo_root/bootstrap.sh" "$src/"
echo "# a command that will go away" > "$src/skills/orch/commands/old.md"
bs="$src/bootstrap.sh"; srun() { "$bs" "$@" --no-herdr >"$log" 2>&1; }
home="$tmp/h11"
srun install --source "$src" --home "$home" --hosts all || fail "install from the temp source"
echo "my own, unrelated" > "$home/.codex/prompts/orch-mine.md"
echo "my own cmd, unrelated" > "$home/.commandcode/commands/orch-mine.md"
echo "a line the next release adds" >> "$src/skills/orch/commands/start.md"
rm "$src/skills/orch/commands/old.md"
if srun check --source "$src" --home "$home" --hosts all; then fail "check should flag the outdated and the dropped prompts"; fi
has "Codex prompt outdated: $home/.codex/prompts/orch-start.md (a shipped older copy; update replaces it and keeps a backup)"
has "Codex prompt stale: $home/.codex/prompts/orch-old.md (its command no longer exists; update removes it and keeps a backup)"
has "Command Code command stale: $home/.commandcode/commands/orch-old.md (its command no longer exists; update removes it and keeps a backup)"
has "Codex prompt kept (not shipped): $home/.codex/prompts/orch-mine.md (no orch command by that name; left as it is)"
has "Command Code command kept (not shipped): $home/.commandcode/commands/orch-mine.md (no orch command by that name; left as it is)"
[[ "$(grep -c 'orch-mine' "$log")" == 2 ]] || fail "each user file is not reported exactly once: $(grep 'orch-mine' "$log")"
[[ "$(grep -c 'kept (not shipped)' "$log")" == 2 ]] || fail "check reported a shipped copy as the user's: $(grep 'kept (not shipped)' "$log")"
if grep -E '(stale|outdated|differs).*orch-mine' "$log"; then fail "check treated the user's file as a shipped one"; fi
srun update --source "$src" --home "$home" --hosts all || fail "update from the temp source"
cmp -s "$src/skills/orch/commands/start.md" "$home/.codex/prompts/orch-start.md" || fail "update did not replace the shipped older copy"
grep -q -x "a line the next release adds" "$home/.codex/prompts/orch-start.md" || fail "new text missing after update"
test ! -e "$home/.codex/prompts/orch-old.md" -a ! -e "$home/.commandcode/commands/orch-old.md" || fail "update left a dropped command's prompt"
grep -q -x '# a command that will go away' "$home"/.agents/orch-prompt-backups/*/*orch-old.md || fail "no backup of the removed prompt"
test -f "$home/.codex/prompts/orch-mine.md" || fail "update removed a user file"
# the update's backups share one folder (start replaced for two hosts, old removed for two hosts)
[[ "$(ls -d "$home"/.agents/orch-prompt-backups/*/ | wc -l | tr -d ' ')" == 1 ]] || fail "update wrote more than one backup folder: $(ls "$home"/.agents)"
[[ "$(ls "$home"/.agents/orch-prompt-backups/*/ | wc -l | tr -d ' ')" == 4 ]] || fail "expected 4 backups in one folder: $(ls "$home"/.agents/orch-prompt-backups/*/)"
test -z "$(ls "$home"/.agents/prompt-backup-* 2>/dev/null)" || fail "backups still land loose in ~/.agents"
grep -q -x "Codex prompt kept (not shipped): $home/.codex/prompts/orch-mine.md (no orch command by that name; left as it is)" "$log" || fail "update did not name the user's file"
grep -q -x "Command Code command kept (not shipped): $home/.commandcode/commands/orch-mine.md (no orch command by that name; left as it is)" "$log" || fail "update did not name the user's cmd file"
[[ "$(grep -c 'kept (not shipped)' "$log")" == 2 ]] || fail "update reported a shipped copy as the user's: $(grep 'kept (not shipped)' "$log")"
grep -q -x "my own, unrelated" "$home/.codex/prompts/orch-mine.md" || fail "update changed a user file"
n="$(grep -l -v 'a line the next release adds' "$home"/.agents/orch-prompt-backups/*/*orch-start.md | wc -l | tr -d ' ')"
[[ "$n" -ge 1 ]] || fail "no backup of the replaced prompt"
srun check --source "$src" --home "$home" --hosts all || fail "check should pass after the update"
# a copy of an older release made before the manifest existed is still recognised as shipped
home="$tmp/h11b"; mkdir -p "$home/.codex/prompts"
cp "$repo_root/tests/fixtures/prompts/orch-start-bfcb091.md" "$home/.codex/prompts/orch-start.md"
run install --source "$repo_root" --home "$home" --hosts codex || fail "install over an older shipped copy"
has "Codex prompt updated: $home/.codex/prompts/orch-start.md (previous kept at $(ls "$home"/.agents/orch-prompt-backups/*/*orch-start.md))"
cmp -s "$repo_root/skills/orch/commands/start.md" "$home/.codex/prompts/orch-start.md" || fail "the older shipped copy was not replaced"

# 12. with the orch skill already current, update still repairs an outdated copy and drops an orphan
home="$tmp/h12"
run install --source "$repo_root" --home "$home" --hosts codex || fail "stage h12"
cp "$repo_root/tests/fixtures/prompts/orch-start-bfcb091.md" "$home/.codex/prompts/orch-start.md"
cp "$repo_root/tests/fixtures/prompts/orch-start-bfcb091.md" "$home/.codex/prompts/orch-gone.md"
if run check --source "$repo_root" --home "$home" --hosts codex; then fail "check should flag the outdated and the orphan"; fi
has "Already current: orch"
has "Codex prompt outdated: $home/.codex/prompts/orch-start.md (a shipped older copy; update replaces it and keeps a backup)"
has "Codex prompt stale: $home/.codex/prompts/orch-gone.md (its command no longer exists; update removes it and keeps a backup)"
run update --source "$repo_root" --home "$home" --hosts codex || fail "update with a current skill"
cmp -s "$repo_root/skills/orch/commands/start.md" "$home/.codex/prompts/orch-start.md" || fail "update left the outdated prompt"
test ! -e "$home/.codex/prompts/orch-gone.md" || fail "update left the orphan prompt"
run check --source "$repo_root" --home "$home" --hosts codex || fail "check after update with a current skill"
# each alone must trigger the repair
home="$tmp/h12a"; run install --source "$repo_root" --home "$home" --hosts codex || fail "stage h12a"
cp "$repo_root/tests/fixtures/prompts/orch-start-bfcb091.md" "$home/.codex/prompts/orch-start.md"
run update --source "$repo_root" --home "$home" --hosts codex || fail "update with only an outdated prompt"
cmp -s "$repo_root/skills/orch/commands/start.md" "$home/.codex/prompts/orch-start.md" || fail "an outdated prompt alone did not trigger the repair"
home="$tmp/h12b"; run install --source "$repo_root" --home "$home" --hosts codex || fail "stage h12b"
cp "$repo_root/tests/fixtures/prompts/orch-start-bfcb091.md" "$home/.codex/prompts/orch-gone.md"
run update --source "$repo_root" --home "$home" --hosts codex || fail "update with only an orphan"
test ! -e "$home/.codex/prompts/orch-gone.md" || fail "an orphan alone did not trigger the removal"

echo "host tests: pass"
