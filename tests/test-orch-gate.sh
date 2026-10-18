#!/usr/bin/env bash
# Split gate and diff-review gate (orch-gate.py): ordered pair, shared file, disjoint pair,
# queue -> blocker merge -> launch, recovery while queued, and each merge refusal. Offline;
# every repo and ledger lives in a mktemp dir. Each guard is mutation-checked (see the commit).
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
orch="$repo_root/skills/orch"
gate="$orch/scripts/orch-gate.py"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null PYTHONDONTWRITEBYTECODE=1
fail() { echo "FAIL: $*" >&2; exit 1; }
eq() { [[ "$1" == "$2" ]] || fail "$3: expected [$2], got [$1]"; }
has() { grep -q -F -- "$2" "$1" || fail "$(basename "$1"): missing: $2"; }
run() { rc=0; out="$(python3 "$gate" "$@" 2>&1)" || rc=$?; }

# ledger <dir> <row>... : an agents ledger whose Pane agents rows are the arguments
ledger() {
  local d="$1" r; shift; mkdir -p "$d"
  { echo '# Orchestrator ledger: gate-test'; echo; echo 'Next action (w1:p1): watch'; echo
    echo '## Pane agents'; echo
    echo '| name | owner | kind/model | pane | worktree / branch | brief | handoff | status | last event | depends | owns |'
    echo '|---|---|---|---|---|---|---|---|---|---|---|'
    for r in "$@"; do echo "$r"; done
    echo; echo '## Watcher'; echo 'pane w1:p3, pid 1, wakes: w1:p1, agents: none'; } > "$d/ledger.md"
}
row() { # <name> <status> <depends> <owns>
  echo "| $1 | w1:p1 | claude/sonnet | - | ../r.wt/$1 / $1 | b.md | h.md | $2 | 06 14:02 x | $3 | $4 |"
}
verdict() { echo "$out" | head -1 | cut -d: -f1; }

# --- split gate: admit ---
d="$tmp/l1"; ledger "$d" "$(row a working none 'src/a/**')"
run admit "$d" b --owns 'docs/**';                eq "$rc|$(verdict)" '0|run' "disjoint pair runs now"
eq "$(echo "$out" | sed -n 2p)" 'status: working' "disjoint pair status"
run admit "$d" b --owns 'src/ab/x.py';            eq "$rc|$(verdict)" '0|run' "src/ab does not overlap src/a/**"
run admit "$d" b --owns 'src/b/*.py';             eq "$rc|$(verdict)" '0|run' "sibling globs are disjoint"
run admit "$d" b --owns 'docs/x.md' --depends a;  eq "$rc|$(verdict)" '3|queue' "ordered pair queues"
eq "$(echo "$out" | sed -n 2p)" 'status: queued: after a' "ordered pair status"
run admit "$d" b --owns 'src/a/x.py';             eq "$rc|$(verdict)" '3|sequential' "file under a glob dir is sequential"
eq "$(echo "$out" | sed -n 2p)" 'status: queued: after a' "shared path status"
run admit "$d" b --owns 'src/a';                  eq "$rc|$(verdict)" '3|sequential' "dir above an owned glob"
run admit "$d" b --owns 'src/*.py';               eq "$rc|$(verdict)" '3|sequential' "glob over a dir holding an owned glob"
run admit "$d" b --owns './src/a/**';             eq "$rc|$(verdict)" '3|sequential' "same glob, ./ prefix"
d="$tmp/l2"; ledger "$d" "$(row a working none 'src/x.py')"
run admit "$d" b --owns 'src/x.py';               eq "$rc|$(verdict)" '3|sequential' "shared file is sequential"
run admit "$d" b --owns 'src/*.py';               eq "$rc|$(verdict)" '3|sequential' "glob over a shared file"
run admit "$d" b --owns 'src/y.py';               eq "$rc|$(verdict)" '0|run' "other file in the same dir runs"
run admit "$d" b --owns 'src';                    eq "$rc|$(verdict)" '3|sequential' "plain dir above an owned file"
d="$tmp/l2b"; ledger "$d" "$(row a working none 'src')"
run admit "$d" b --owns 'src/x.py';               eq "$rc|$(verdict)" '3|sequential' "plain file under an owned dir"
run admit "$d" b --owns 'srcs/x.py';              eq "$rc|$(verdict)" '0|run' "srcs is not under src"
# a dependency that merged, closed or is gone no longer holds; an unknown one is an error
d="$tmp/l3"; ledger "$d" "$(row a merged none 'src/x.py')" "$(row c closed none 'src/x.py')" "$(row g gone none 'src/x.py')"
run admit "$d" b --owns 'src/x.py' --depends a;   eq "$rc|$(verdict)" '0|run' "merged dependency and ended rows do not hold"
run admit "$d" b --owns 'src/x.py' --depends zz;  eq "$rc" 2 "unknown dependency is exit 2"
run admit "$d" b;                                  eq "$rc" 2 "missing --owns is exit 2"
# a done-but-unmerged row still owns its paths; a queued row is active too
d="$tmp/l4"; ledger "$d" "$(row a done none 'src/x.py')" "$(row q 'queued: after a' none 'src/q.py')"
run admit "$d" b --owns 'src/x.py';               eq "$rc|$(verdict)" '3|sequential' "done is not merged"
run admit "$d" b --owns 'src/q.py';               eq "$rc|$(verdict)" '3|sequential' "a queued row keeps its place"
eq "$(echo "$out" | sed -n 2p)" 'status: queued: after q' "behind the queued row"
# an active task that records no owned paths holds everything
d="$tmp/l5"; ledger "$d" "$(row a working none none)"
run admit "$d" b --owns 'docs/x.md';              eq "$rc|$(verdict)" '3|sequential' "no recorded owns holds"
# a minimal ledger has no gate
mkdir -p "$tmp/min"; cp "$orch/ledger-minimal-template.md" "$tmp/min/ledger.md"
run admit "$tmp/min" b --owns x;                  eq "$rc" 2 "minimal ledger is exit 2"
# the Sub-agents table counts too
d="$tmp/l6"; ledger "$d"
python3 - "$d/ledger.md" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("## Watcher", "## Sub-agents and background jobs\n| name | owner | type | started | report | status | depends | owns |\n|---|---|---|---|---|---|---|---|\n| w1 | w1:p1 | worker | 14:00 | r.md | working | none | lib/** |\n\n## Watcher")
open(p, "w").write(s)
PY
run admit "$d" b --owns 'lib/a.py';               eq "$rc|$(verdict)" '3|sequential' "worker sub-agent owns paths"

# --- queue -> blocker merge -> launch; recovery while queued ---
d="$tmp/q1"; ledger "$d" "$(row a working none 'src/**')" "$(row b 'queued: after a' none 'src/b.py')" \
  "$(row c 'queued: after a' none 'src/b.py')" "$(row e 'queued: after a' none 'src/e.py')"
run release "$d"
eq "$out" $'hold b after a\nhold c after a\nhold e after a' "blocker still working: all hold"
sed -i 's/^| a | w1:p1 \(.*\)| working |/| a | w1:p1 \1| merged |/' "$d/ledger.md"
cp "$d/ledger.md" "$d/ledger.before"
# a fresh process with only the ledger on disk (the orchestrator restarted while rows were queued)
run release "$d"
eq "$out" $'release b\nhold c after b\nrelease e' "blocker merged: b and e launch, c waits behind b"
cmp -s "$d/ledger.md" "$d/ledger.before" || fail "release without --apply changed the ledger"
run release "$d" --apply
eq "$(grep '^| c ' "$d/ledger.md" | cut -d'|' -f9 | xargs)" 'queued: after b' "--apply retargets c's blocker"
eq "$(grep -c 'queued: after a' "$d/ledger.md")" 2 "--apply leaves released rows for task.md (b, e)"
# b launches (status working); b merges; c is released
sed -i 's/^| b \(.*\)| queued: after a |/| b \1| working |/; s/^| e \(.*\)| queued: after a |/| e \1| working |/' "$d/ledger.md"
run release "$d";                                  eq "$out" 'hold c after b' "b working: c still held"
sed -i 's/^| b \(.*\)| working |/| b \1| merged |/' "$d/ledger.md"
run release "$d";                                  eq "$out" 'release c' "b merged: c launches"
# the blocker is gone or closed, not merged: also released
sed -i 's/^| b \(.*\)| merged |/| b \1| gone |/' "$d/ledger.md"
run release "$d";                                  eq "$out" 'release c' "blocker gone: c launches"
# a dependency that is itself queued still blocks
d="$tmp/q2"; ledger "$d" "$(row a working none 'x/**')" "$(row b 'queued: after a' a 'y/**')" "$(row c 'queued: after b' b 'z/**')"
run release "$d";                                  eq "$out" $'hold b after a\nhold c after b' "dependent on a queued row holds"
run release "$tmp/q-none" 2>/dev/null;             eq "$rc" 2 "no ledger is exit 2"
d="$tmp/q3"; ledger "$d" "$(row a working none 'x/**')"
run release "$d";                                  eq "$out" 'none queued' "nothing queued"

# --- diff review before merge ---
r="$tmp/repo"; mkdir -p "$r"; g() { git -C "$r" "$@"; }
g init -q -b main; g config user.email t@example.invalid; g config user.name tester
echo 0 > "$r/f"; g add f; g -c commit.gpgsign=false commit -q -m base
g checkout -q -b feat; echo 1 > "$r/f"; g commit -qam one; echo 2 > "$r/f"; g commit -qam two
fork="$(g rev-parse main)"; first="$(g rev-parse feat~1)"; tip="$(g rev-parse feat)"
d="$tmp/rv"; ledger "$d" "$(row a done none 'f')"
mc() { run merge-check "$d" "${1:-a}" --repo "$r" --branch feat; }
rev() { # <agent> <range> <author> <reviewer> <verdict>
  run review "$d" "$1" --repo "$r" --range "$2" --author "$3" --reviewer "$4" --verdict "$5"; }
mc;                                                 eq "$rc" 4 "no review: refused"
echo "$out" | grep -q '^refuse: no diff review recorded for a$' || fail "no-review message: $out"
rev a "$fork..$tip" claude/sonnet-5.5 claude/sonnet-5.5 pass
eq "$rc" 2 "reviewer on the author's model is refused"
[[ ! -e "$d/reviews.log" ]] || fail "a refused review was recorded"
rev a "$fork..$tip" claude/sonnet-5.5 codex/gpt-6.1-sol fail; eq "$rc" 0 "record a failed review"
mc;                                                 eq "$rc" 5 "failed review: refused"
rev a "$fork..$tip" claude/sonnet-5.5 claude/opus-5.5 pass;   eq "$rc" 0 "record a passing review"
mc;                                                 eq "$rc" 0 "passing review of the whole branch: ok"
echo "$out" | grep -q "^ok: a ${fork:0:9}\.\.${tip:0:9} reviewed by claude/opus-5.5$" || fail "ok message: $out"
mc ab;                                              eq "$rc" 4 "another agent's review does not count (a vs ab)"
rev ab "$fork..$tip" claude/sonnet-5.5 claude/opus-5.5 pass
d2="$d"; d="$tmp/rv2"; ledger "$d" "$(row a done none 'f')"; rev ab "$fork..$tip" claude/sonnet-5.5 claude/opus-5.5 pass
mc;                                                 eq "$rc" 4 "a review of ab does not count for a (prefix name)"
d="$d2"
rev a "$fork..$tip" claude/sonnet-5.5 codex/gpt-6.1-sol fail; mc
eq "$rc" 5 "the latest review wins: pass then fail"
rev a "$fork..$tip" claude/sonnet-5.5 claude/opus-5.5 pass; mc; eq "$rc" 0 "the latest review wins: fail then pass"
rev a "$first..$tip" claude/sonnet-5.5 claude/opus-5.5 pass; mc
eq "$rc" 7 "review starts after the fork point: refused"
rev a "$fork..$tip" claude/sonnet-5.5 claude/opus-5.5 pass
echo 3 > "$r/f"; g commit -qam three
mc;                                                 eq "$rc" 6 "commit after the review: refused"
echo "$out" | grep -q "commits after the review$" || fail "stale message: $out"
rev a "$fork..feat" claude/sonnet-5.5 claude/opus-5.5 pass; mc; eq "$rc" 0 "re-review of the new tip: ok"
g commit -q --amend -m rewritten; mc;               eq "$rc" 6 "rewritten tip: refused"
run review "$d" a --repo "$r" --range "nonsense" --author x/y --reviewer p/q --verdict pass; eq "$rc" 2 "bad range"
run review "$d" a --repo "$r" --range "$fork..feat" --author x/y --reviewer p/q --verdict maybe; eq "$rc" 2 "bad verdict"

# --- instruction text ---
has "$orch/commands/task.md" 'orch-gate.py admit <dir> <agent> --owns'
has "$orch/commands/task.md" '`queued: after <task>`'
has "$orch/commands/task.md" 'no pane, no worktree, no watcher'
has "$orch/commands/event.md" 'orch-gate.py review <dir> <agent>'
has "$orch/commands/event.md" 'orch-gate.py merge-check <dir> <agent>'
has "$orch/commands/event.md" 'Merge only on exit 0. Exit 4 no review, 5 review failed, 6 a commit came after the review,'
has "$orch/commands/event.md" 'orch-gate.py release <dir> --apply'
has "$orch/ledger-template.md" '| name | owner | kind/model | pane | worktree / branch | brief | handoff | status | last event | depends | owns |'
has "$orch/ledger-template.md" '`queued: after <task>`'
has "$orch/SKILL.md" '`scripts/orch-gate.py`'
echo "ok: gate"
