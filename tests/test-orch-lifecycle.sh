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
echo "ok: lifecycle"
