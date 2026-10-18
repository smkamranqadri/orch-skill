#!/usr/bin/env bash
# Front door: KIS version helper, minimal ledger accepted by check, no lore or rule-number text.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
orch="$repo_root/skills/orch"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected [$2], got [$1]"; }

# --- KIS version helper (orch-kis-version.sh) ---
kis_repo() { # <name> <version-line>
  mkdir -p "$tmp/$1/.agents/skills/kis"
  printf -- '---\nname: kis\nmetadata:\n%s\n---\n' "$2" > "$tmp/$1/.agents/skills/kis/SKILL.md"
}
ver() { # <name> -> "<stdout>|<exit>"
  local out rc=0
  out="$("$orch/scripts/orch-kis-version.sh" "$tmp/$1")" || rc=$?
  echo "$out|$rc"
}
kis_repo old '  version: "0.10.1"';   eq "$(ver old)" 'kis 0.10.1|3' "0.10.1 offers the update"
kis_repo low '  version: "0.9.12"';   eq "$(ver low)" 'kis 0.9.12|3' "0.9.12 offers the update"
kis_repo cur '  version: "0.11.0"';   eq "$(ver cur)" 'kis 0.11.0|0' "0.11.0 offers nothing"
kis_repo new '  version: "0.12.3"';   eq "$(ver new)" 'kis 0.12.3|0' "0.12.3 offers nothing"
kis_repo big '  version: "0.100.0"';  eq "$(ver big)" 'kis 0.100.0|0' "0.100.0 sorts as a version, not text"
kis_repo bare '  version: 0.11.0';     eq "$(ver bare)" 'kis 0.11.0|0' "unquoted version"
kis_repo none '  other: 1';           eq "$(ver none)" 'kis unknown|3' "unreadable version offers the update"
mkdir -p "$tmp/nokis"; eq "$(ver nokis)" 'kis none|2' "no KIS package"
# The vendored copy in this repo is current.
"$orch/scripts/orch-kis-version.sh" "$repo_root" >/dev/null || fail "this repo's vendored KIS is below 0.11.0"

# --- minimal ledger: check accepts it with no watcher ---
mk() { # <dir> <next> <plan> <review>
  mkdir -p "$1"
  cat > "$1/ledger.md" <<LEDGER
# Minimal ledger: demo
Ledger: minimal
Updated: 2026-10-18T10:00:00Z by test

Task: fix the demo
Next action: $2
Plan: $3
Plan review: $4

## Decisions
- 2026-10-18 "keep it small"

## Done
- 2026-10-18 nothing yet
LEDGER
}
chk() { local rc=0 out; out="$(python3 "$orch/scripts/orch-watch.py" check "$1" 2>&1)" || rc=$?; echo "$out|$rc"; }
mk "$tmp/m1" 'write the test' none none
eq "$(chk "$tmp/m1")" 'check: clean|0' "minimal ledger, no plan"
[[ ! -e "$tmp/m1/watcher.pid" && ! -e "$tmp/m1/agents.txt" ]] || fail "check created watcher files"
mk "$tmp/m2" 'implement' plan.md 'none'
eq "$(chk "$tmp/m2")" 'run: [plan-review] written plan plan.md has no recorded review with '"'outcome: ready'"'; review it before implementing|1' "plan without review is refused"
mk "$tmp/m3" 'implement' plan.md 'reviewer codex/gpt-6.1-sol/high; outcome: rework; 2026-10-18'
eq "$(chk "$tmp/m3")" "run: [plan-review] written plan plan.md has no recorded review with 'outcome: ready'; review it before implementing|1" "rework outcome is refused"
mk "$tmp/m4" 'implement' plan.md 'reviewer codex/gpt-6.1-sol/high; outcome: ready; 2026-10-18'
eq "$(chk "$tmp/m4")" 'check: clean|0' "recorded ready review passes"
mk "$tmp/m5" '' none none
eq "$(chk "$tmp/m5")" "run: [next-action] no 'Next action:' line, or it is empty|1" "empty Next action"
mk "$tmp/m6" 'x' none none; for i in $(seq 55); do echo "- filler $i" >> "$tmp/m6/ledger.md"; done
eq "$(chk "$tmp/m6" | head -1)" 'run: [ledger-length] ledger has 69 lines, the limit is 60|1' "over 60 lines"
# A full ledger (no Ledger: minimal line) is still checked as before: no Pane agents table, exit 3.
mkdir -p "$tmp/full"; printf '# Orchestrator ledger\nNext action (w1:p1): x\n' > "$tmp/full/ledger.md"
eq "$(chk "$tmp/full" | sed 's/^.*|//')" '3' "full ledger still needs its table"
# The shipped template, with only Task and Next filled (as start.md says), is clean: it ships
# `Plan: none` and `Plan review: none`, so a one-line fix needs no plan or review.
mkdir -p "$tmp/tpl"
sed -e 's/<project>/demo/' -e 's/<one line>/t/' -e 's/<one line; never empty>/go/' \
    "$orch/ledger-minimal-template.md" > "$tmp/tpl/ledger.md"
eq "$(chk "$tmp/tpl")" 'check: clean|0' "template with Task and Next only"
grep -q -x 'Plan: none' "$tmp/tpl/ledger.md" || fail "template does not ship 'Plan: none'"
grep -q -x 'Plan review: none' "$tmp/tpl/ledger.md" || fail "template does not ship 'Plan review: none'"
# The review gate takes only an exact outcome: the format placeholder, a prefix match and a
# blocked review do not satisfy it; ready and a user waiver do.
G="run: [plan-review] written plan plan.md has no recorded review with 'outcome: ready'; review it before implementing|1"
mk "$tmp/g1" 'x' plan.md 'reviewer x; outcome: ready|rework; 2026-10-18'; eq "$(chk "$tmp/g1")" "$G" "format placeholder ready|rework"
mk "$tmp/g2" 'x' plan.md 'reviewer x; outcome: ready-ish; 2026-10-18'; eq "$(chk "$tmp/g2")" "$G" "ready-ish"
mk "$tmp/g3" 'x' plan.md 'blocked; reviewer stalled; 2026-10-18'; eq "$(chk "$tmp/g3")" "$G" "blocked review"
mk "$tmp/g4" 'x' plan.md 'reviewer x; outcome: ready'; eq "$(chk "$tmp/g4")" 'check: clean|0' "ready at end of line"
mk "$tmp/g5" 'x' plan.md 'reviewer x; outcome: waived; 2026-10-18'; eq "$(chk "$tmp/g5")" 'check: clean|0' "user waiver"
mk "$tmp/g6" 'x' plan.md 'reviewer x; outcome:ready ; 2026-10-18'; eq "$(chk "$tmp/g6")" 'check: clean|0' "spacing around ready"

# --- start.md and SKILL.md: Fast mode writes no plan, the reviewer is proposed not launched, a
# review that cannot run is recorded and the user asked ---
st="$orch/commands/start.md"; sk="$orch/SKILL.md"
for f in "$st" "$sk"; do
  grep -q -F 'Fast-mode work (a small, obvious fix)' "$f" || fail "$(basename "$f"): Fast-mode work needs no plan"
  grep -q -F 'blocked' "$f" || fail "$(basename "$f"): a review that cannot run is recorded as blocked"
  grep -q -F 'review later, waive' "$f" || fail "$(basename "$f"): the user is asked review later, waive or stop"
done
grep -q -F 'and launch it only after they approve' "$st" || fail "start.md: reviewer launched only after approval"
grep -q -F 'is proposed to the user and launched only after approval' "$sk" || fail "SKILL.md: reviewer launched only after approval"
grep -q -F 'never' "$st" && grep -q -F 'start another CLI on your own' "$st" || fail "start.md: never auto-launch a reviewer"
grep -q -F 'never on your own' "$sk" || fail "SKILL.md: never auto-launch a reviewer"

# --- the files this layer owns: no lore command, retro step or rule numbers ---
owned=("$orch/SKILL.md" "$orch/commands/start.md" "$orch/commands/status.md" "$orch/commands/task.md"
       "$orch/commands/event.md" "$orch/commands/watch.md" "$orch/ledger-template.md"
       "$orch/ledger-minimal-template.md" "$orch"/references/*)
if grep -nE '/lore:(load|retro)|(^|[^A-Za-z])lore notes|[Rr]ules? [0-9]+|[Pp]references? [0-9]+|[Tt]hought [0-9]+' "${owned[@]}"; then
  fail "owned files cite lore commands or rule numbers"
fi
# --- SKILL.md stays short and carries the new version ---
lines="$(wc -l < "$orch/SKILL.md")"; (( lines < 150 )) || fail "SKILL.md has $lines lines"
grep -qE '^  version: "0\.12\.0"$' "$orch/SKILL.md" || fail "SKILL.md version is not 0.12.0"
# Herdr is required only in Agents mode: no unconditional stop in SKILL.md.
if grep -nE '^.*Herdr missing: say so and stop\.' "$orch/SKILL.md"; then fail "unconditional Herdr stop"; fi
grep -q 'Herdr.*required in Agents mode only' "$orch/SKILL.md" || fail "Agents-only Herdr rule missing"
echo "ok: front door"
