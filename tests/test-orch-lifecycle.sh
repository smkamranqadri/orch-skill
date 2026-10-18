#!/usr/bin/env bash
# Run lifecycle text guards (P2 review): close ends a finished run, restores Task and Next, handoff
# does not flush decisions, start moves Task and Next into the ledger, start asks before launching
# a reviewer. These pin the instruction text; each guard is mutation-checked.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
orch="$repo_root/skills/orch"
fail() { echo "FAIL: $*" >&2; exit 1; }
has() { grep -q -F -- "$2" "$1" || fail "$(basename "$1"): missing: $2"; }
hasnt() { if grep -q -F -- "$2" "$1"; then fail "$(basename "$1"): unexpected: $2"; fi; }

close="$orch/commands/close.md"
# 1. step 2 is not tied to live rows or to step 1 having run
hasnt "$close" '(only when step 1 ran)'
hasnt "$close" 'None: skip to step 3'
has "$close" '2. **End the run'"'"'s records.** Runs whenever `D/ledger.md` is an agents ledger'
has "$close" "even when every row is already \`closed\` or"
has "$close" 'Stop the watcher when `<D>/watcher.pid` exists'
has "$close" '1. **Close agents** (only live ones).'
# 2. close restores Task and Next from the ledger, and removes what it flushed
has "$close" "write State's Task and Next from the ledger's"
has "$close" 'delete each moved entry from the ledger so a later close cannot move it twice'
# 3. handoff keeps decisions in the ledger; the templates say close, not handoff
hasnt "$orch/commands/handoff.md" 'Flush applied decisions'
has "$orch/commands/handoff.md" 'only `close` flushes them to Intent'
has "$orch/ledger-template.md" 'flush to the KIS plan at close)'
hasnt "$orch/ledger-template.md" 'at handoff'
# 4. start moves State's Task and Next into the ledger when it writes the pointer
has "$orch/commands/start.md" "First move State's Task and Next into"
has "$orch/SKILL.md" "\`start\` moves State's"
# 5. SKILL.md names the per-host invocations
has "$orch/SKILL.md" 'Codex: `/prompts:orch-start`; Command Code: `/orch-start`'
# 6. exit 2 with kis/ present is offered the install; pointer off is recorded in the ledger and read
#    by event and close; the helper still reports exit 2 for a repo with kis/ and no package
has "$orch/commands/start.md" 'or exit 2 with `kis/` present (no `.agents/skills/kis`): offer that repo'"'"'s'
has "$orch/commands/start.md" 'put `State pointer: off (KIS <version>)` on the line under `Updated:`'
has "$orch/commands/event.md" 'the ledger has no `State pointer: off` line'
has "$orch/commands/close.md" 'A ledger with a `State pointer: off` line means State is not touched.'
has "$orch/SKILL.md" 'notes `State pointer: off (KIS <version>)` under `Updated:` in the'
has "$orch/SKILL.md" '(`orch-kis-version.sh` exit 2) is offered the same install.'
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/kisdir/kis/state"; echo x > "$tmp/kisdir/kis/state/current.md"
out="$("$orch/scripts/orch-kis-version.sh" "$tmp/kisdir")" && rc=0 || rc=$?
[[ "$out|$rc" == 'kis none|2' ]] || fail "kis/ without a package: expected [kis none|2], got [$out|$rc]"
# a full ledger with the pointer-off line still checks like one without it
mkdir -p "$tmp/led"; cp "$repo_root"/tests/fixtures/visibility/* "$tmp/led/"
a="$(python3 "$orch/scripts/orch-watch.py" check "$tmp/led" --offline | sed 's/ledger has [0-9]* lines/ledger has N lines/')"
sed -i '2a State pointer: off (KIS 0.10.1)' "$tmp/led/ledger.md"
b="$(python3 "$orch/scripts/orch-watch.py" check "$tmp/led" --offline | sed 's/ledger has [0-9]* lines/ledger has N lines/')"
[[ "$a" == "$b" ]] || fail "the pointer-off header line changed check output"
echo "ok: lifecycle"
