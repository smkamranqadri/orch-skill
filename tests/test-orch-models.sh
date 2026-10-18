#!/usr/bin/env bash
# orch-models.py: discovery per CLI, merge that keeps notes, unreachable reports, reviewer rules.
# Fixture data is fictional; every run uses a temp HOME and never touches the real one.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
M="$repo_root/skills/orch/scripts/orch-models.py"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
export HOME="$tmp/home"; mkdir -p "$HOME"
unset ORCH_MODELS_FILE
export ORCH_MODELS_TODAY=2031-01-05
fx="$tmp/fx"; mkdir -p "$fx"; export ORCH_MODELS_FIXTURE_DIR="$fx"
mat="$HOME/.agents/orch/models.md"
run() { python3 "$M" "$@"; }

# --- fixtures (real formats, fictional models) -------------------------------------------------
cat > "$fx/codex-models-cache.json" <<'J'
{"fetched_at":"2031-01-04T08:00:00Z","models":[
 {"slug":"zephyr-3-pro","visibility":"list","default_reasoning_level":"low",
  "supported_reasoning_levels":[{"effort":"low"},{"effort":"medium"},{"effort":"high"},{"effort":"xhigh"}]},
 {"slug":"zephyr-3-mini","visibility":"list","default_reasoning_level":"medium",
  "supported_reasoning_levels":[{"effort":"low"},{"effort":"medium"}]},
 {"slug":"zephyr-internal","visibility":"hide","default_reasoning_level":"low",
  "supported_reasoning_levels":[{"effort":"low"}]}]}
J
cat > "$fx/cmd-list-models.txt" <<'T'
Available models  ·  4 models

Open Source

foo-labs/foo-large-2      long-context reasoning (default)
foo-labs/foo-small-2      fast and cheap

Anthropic

quill-2-5                 fictional Anthropic-style entry

Stealth

stealth/hush:free         FREE stealth model

Pass the full id, or just the short name after the last "/":
cmd --model foo-labs/foo-large-2
Docs:  https://example.invalid/docs

Decision models (headless only)
typesafe/oracle  typed questions in, probabilities out
T
printf 'Fetching available models...\nplume-1-flash-high\tPlume 1 Flash (High)\nplume-1-flash-low\tPlume 1 Flash (Low)\nplume-1-flash-medium\tPlume 1 Flash (Medium)\nopen-mid-70b-medium\tOpen Mid 70B (Medium)\nquill-2-5-thinking\tQuill 2.5 (Thinking)\n' > "$fx/agy-models.txt"
printf '  --effort <level>        Effort level for the current session\n                          (low, medium, high, xhigh, max)\n  --model <model>   Model for the session\n' > "$fx/claude-help.txt"
printf '# fictional ids\nquill-2-5\nquill-2-mini  # small one\n' > "$tmp/claude-ids.txt"

# --- 1. discovery: models and efforts per CLI --------------------------------------------------
run discover --claude-models "$tmp/claude-ids.txt" > "$tmp/disc.json"
python3 -I - "$tmp/disc.json" <<'P' || fail "discovery from fixtures"
import json, sys
d = json.load(open(sys.argv[1]))
def eff(h): return {m["id"]: m["efforts"] for m in d[h]["models"]}
assert eff("codex") == {"zephyr-3-pro": ["low","medium","high","xhigh"], "zephyr-3-mini": ["low","medium"]}, eff("codex")
assert eff("cmd") == {"foo-labs/foo-large-2": [], "foo-labs/foo-small-2": [], "quill-2-5": [], "stealth/hush:free": []}, eff("cmd")
assert eff("agy") == {"plume-1-flash": ["low","medium","high"], "open-mid-70b": ["medium"], "quill-2-5-thinking": []}, eff("agy")
five = ["low","medium","high","xhigh","max"]
assert eff("claude") == {"quill-2-5": five, "quill-2-mini": five}, eff("claude")
P

# --- 2. rebuild from scratch lists exactly the installed models, with efforts and price sources
cat > "$tmp/prices1.json" <<'J'
{"sources_failed":[{"source":"prices.example.invalid/open","reason":"HTTP 503"}],
 "prices":[
  {"host":"codex","model":"zephyr-3-pro","in":3,"cached":0.3,"out":15,"source":"pricing.example.invalid/zephyr","date":"2031-01-05"},
  {"host":"claude","model":"quill-2-5","in":2,"cached":0.1,"out":10,"source":"pricing.example.invalid/quill"},
  {"host":"cmd","model":"foo-labs/foo-small-2","in":0.1,"out":0.4,"source":"pricing.example.invalid/open","date":"2031-01-05"},
  {"host":"codex","model":"zephyr-3-mini","in":1,"out":4,"source":""},
  {"host":"codex","model":"no-such-model","in":1,"out":4,"source":"pricing.example.invalid/zephyr"}]}
J
set +e
run rebuild --plan claude=TestMax --plan codex=TestPlus --claude-models "$tmp/claude-ids.txt" --prices "$tmp/prices1.json" > "$tmp/r1.out" 2>&1; rc=$?
set -e
[[ $rc -eq 3 ]] || fail "rebuild with gaps should exit 3, got $rc: $(cat "$tmp/r1.out")"
test -f "$mat" || fail "rebuild did not write the user's matrix"
python3 -I - "$mat" <<'P' || fail "from-scratch matrix content"
import sys
rows = []
for ln in open(sys.argv[1]):
    if ln.startswith("| ") and not ln.startswith(("| Host", "| Job")):
        rows.append([c.strip() for c in ln.strip().strip("|").split(" | ")])
rows = [r for r in rows if len(r) == 9]
got = {(r[0], r[1]): (r[2], r[3], r[4], r[5], r[8]) for r in rows}
want_keys = {("claude","quill-2-5"),("claude","quill-2-mini"),("codex","zephyr-3-pro"),("codex","zephyr-3-mini"),
  ("agy","plume-1-flash"),("agy","open-mid-70b"),("agy","quill-2-5-thinking"),
  ("cmd","foo-labs/foo-large-2"),("cmd","foo-labs/foo-small-2"),("cmd","quill-2-5"),("cmd","stealth/hush:free")}
assert set(got) == want_keys, set(got) ^ want_keys
assert got[("codex","zephyr-3-pro")] == ("low, medium, high, xhigh", "3 / 0.3 / 15", "pricing.example.invalid/zephyr", "2031-01-05", "2031-01-05"), got[("codex","zephyr-3-pro")]
assert got[("claude","quill-2-5")][1:4] == ("2 / 0.1 / 10", "pricing.example.invalid/quill", "2031-01-05"), got[("claude","quill-2-5")]
assert got[("cmd","foo-labs/foo-small-2")][1] == "0.1 / - / 0.4"
assert got[("agy","plume-1-flash")][0] == "low, medium, high"
assert got[("cmd","foo-labs/foo-large-2")][1:3] == ("unknown", "none"), "unpriced model must not get a guessed price"
assert got[("codex","zephyr-3-mini")][1:3] == ("unknown", "none"), "a price without a source must not be recorded"
txt = open(sys.argv[1]).read()
assert "zephyr-internal" not in txt and "typesafe/oracle" not in txt, "hidden or headless-only model listed"
assert "- codex: TestPlus" in txt and "- claude: TestMax" in txt
P
grep -q '^PRICE SOURCE UNREACHABLE prices.example.invalid/open: HTTP 503$' "$tmp/r1.out" || fail "failed price source not reported: $(cat "$tmp/r1.out")"
grep -q '^NO PRICE SOURCE cmd: 3 models' "$tmp/r1.out" || fail "unpriced cmd models not counted: $(cat "$tmp/r1.out")"
grep -q '^NO PRICE SOURCE codex: 1 models' "$tmp/r1.out" || fail "unsourced codex price not reported"
grep -q '^PLAN UNKNOWN agy:' "$tmp/r1.out" && grep -q '^PLAN UNKNOWN cmd:' "$tmp/r1.out" || fail "unknown plans not reported"
grep -q '^PROBLEM price for codex/zephyr-3-mini has no source; not recorded$' "$tmp/r1.out" || fail "sourceless price not flagged"
grep -q '^PROBLEM price for codex/no-such-model ignored: not in the matrix$' "$tmp/r1.out" || fail "price for unknown model not flagged"
# a from-scratch picks table holds only installed candidates (the shipped one names models not in this fixture)
grep -q '^| code-review |' "$mat" && fail "a pick with no installed candidate was copied"

# --- 3. notes survive two rebuilds; new models and prices merge in -----------------------------
python3 -I - "$mat" <<'P'
import sys
p = sys.argv[1]; s = open(p).read()
s = s.replace("| 2031-01-05 |  |  | 2031-01-05 |\n", "| 2031-01-05 |  |  | 2031-01-05 |\n", 1)
lines = s.split("\n")
for i, ln in enumerate(lines):
    if ln.startswith("| codex | zephyr-3-pro |"):
        c = [x.strip() for x in ln.strip().strip("|").split(" | ")]
        c[6] = "my pick for builds \\| tight briefs"; c[7] = "built two tasks; slow on reviews"
        lines[i] = "| " + " | ".join(c) + " |"
s = "\n".join(lines).replace("\n## Sources", "\n## My notes\n\nKeep this free text.\n\n## Sources")
s = s.replace("\n## Picks by job\n\n| Job | First choice | Alternatives |\n|---|---|---|\n",
              "\n## Picks by job\n\n| Job | First choice | Alternatives |\n|---|---|---|\n| build | codex/zephyr-3-pro medium | claude/quill-2-5 medium |\n| code-review | claude/quill-2-5 high | codex/zephyr-3-pro high; claude/quill-2-mini high; agy/ghost-1 low |\n| plan-review | claude/quill-2-5 high | codex/zephyr-3-pro high |\n")
open(p, "w").write(s)
P
grep -q 'my pick for builds' "$mat" || fail "test edit did not apply"
# a new model appears in codex, a price changes; claude is not installed any more (no help file)
python3 -I - "$fx/codex-models-cache.json" <<'P'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d["models"].append({"slug":"zephyr-4","visibility":"list","supported_reasoning_levels":[{"effort":"medium"}]})
json.dump(d, open(p, "w"))
P
mv "$fx/claude-help.txt" "$tmp/claude-help.txt.off"
cat > "$tmp/prices2.json" <<'J'
{"prices":[{"host":"codex","model":"zephyr-3-pro","in":4,"cached":0.4,"out":20,"source":"pricing.example.invalid/zephyr","date":"2031-02-01"}]}
J
set +e; run rebuild --plan agy=TestAgy --plan cmd=TestCredits --prices "$tmp/prices2.json" > "$tmp/r2.out" 2>&1; set -e
run rebuild --prices "$tmp/prices2.json" > "$tmp/r3.out" 2>&1 || true
cp "$mat" "$tmp/after2"
run rebuild --prices "$tmp/prices2.json" > "$tmp/r4.out" 2>&1 || true
cmp -s "$mat" "$tmp/after2" || { diff "$tmp/after2" "$mat" >&2; fail "a rebuild with unchanged inputs changed the file"; }
grep -q '^| codex | zephyr-3-pro | low, medium, high, xhigh | 4 / 0.4 / 20 | pricing.example.invalid/zephyr | 2031-02-01 | my pick for builds \\| tight briefs | built two tasks; slow on reviews | 2031-01-05 |$' "$mat" \
  || fail "notes lost or price not merged: $(grep zephyr-3-pro "$mat")"
grep -q '^| codex | zephyr-4 | medium | unknown | none | - |  |  | 2031-01-05 |$' "$mat" || fail "new model not merged: $(grep zephyr-4 "$mat")"
grep -q '^Keep this free text.$' "$mat" || fail "free section lost"
grep -q '^| code-review | claude/quill-2-5 high | codex/zephyr-3-pro high; claude/quill-2-mini high; agy/ghost-1 low |$' "$mat" || fail "user picks changed"
# the claude rows stay while claude is unreachable, and the report says why
grep -q '^| claude | quill-2-5 |' "$mat" || fail "rows of an unreachable CLI were dropped"
grep -q '^not installed (skipped): claude$' "$tmp/r2.out" || fail "missing CLI not reported: $(cat "$tmp/r2.out")"
grep -q '^PROBLEM pick code-review: agy/ghost-1 low not in the matrix$' "$tmp/r2.out" || fail "stale pick not reported: $(cat "$tmp/r2.out")"
# a model that vanishes from a reachable CLI is kept and reported
python3 -I - "$fx/codex-models-cache.json" <<'P'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["models"] = [m for m in d["models"] if m["slug"] != "zephyr-3-mini"]; json.dump(d, open(p, "w"))
P
run rebuild > "$tmp/r5.out" 2>&1 || true
grep -q '^not discovered this run, kept: codex/zephyr-3-mini$' "$tmp/r5.out" || fail "vanished model not reported: $(cat "$tmp/r5.out")"
grep -q '^| codex | zephyr-3-mini |' "$mat" || fail "vanished model deleted"

# --- 4. an orch update keeps the user's matrix --------------------------------------------------
ih="$tmp/ihome"; mkdir -p "$ih/.agents/orch"
cp "$mat" "$ih/.agents/orch/models.md"; before="$(cksum < "$ih/.agents/orch/models.md")"
"$repo_root/bootstrap.sh" install --source "$repo_root" --home "$ih" --no-herdr >"$tmp/inst.log" 2>&1 || fail "install: $(cat "$tmp/inst.log")"
"$repo_root/bootstrap.sh" update --source "$repo_root" --home "$ih" --no-herdr >"$tmp/upd.log" 2>&1 || fail "update: $(cat "$tmp/upd.log")"
[[ "$(cksum < "$ih/.agents/orch/models.md")" == "$before" ]] || fail "update changed the user's matrix"
test -f "$ih/.agents/skills/orch/references/models.md" || fail "shipped matrix not installed"
test -x "$ih/.agents/skills/orch/scripts/orch-models.py" || fail "installed helper is not executable"
test -f "$ih/.agents/skills/orch/commands/models.md" || fail "models command not installed"
out="$(HOME="$ih" python3 "$ih/.agents/skills/orch/scripts/orch-models.py" path)"
[[ "$out" == "$ih/.agents/orch/models.md (user)" ]] || fail "installed helper does not read the user's matrix: $out"
out="$(HOME="$ih" python3 "$ih/.agents/skills/orch/scripts/orch-models.py" pick build)"
[[ "$out" == "codex zephyr-3-pro medium" ]] || fail "pick does not follow the user's table: $out"

# --- 5. a broken cache is unreachable, not guessed ---------------------------------------------
echo '{"models": "oops"' > "$fx/codex-models-cache.json"
set +e; run rebuild > "$tmp/r6.out" 2>&1; rc=$?; set -e
[[ $rc -eq 3 ]] || fail "unreachable CLI should exit 3, got $rc"
grep -q '^UNREACHABLE codex: models_cache.json unreadable' "$tmp/r6.out" || fail "unreadable codex cache not reported: $(cat "$tmp/r6.out")"
grep -q '^| codex | zephyr-4 |' "$mat" || fail "unreachable CLI lost its rows"
printf 'Available models  ·  9 models\n\nOpen\n\nfoo-labs/foo-large-2   x\n' > "$fx/cmd-list-models.txt"
set +e; run rebuild > "$tmp/r7.out" 2>&1; set -e
grep -q '^UNREACHABLE cmd: parsed 1 models but the list header says 9' "$tmp/r7.out" || fail "format drift in cmd not reported: $(cat "$tmp/r7.out")"

# --- 6. picks: reviewer rules -------------------------------------------------------------------
cat > "$tmp/pm.md" <<'MD'
# Pick fixture

## Matrix

| Host | Model | Efforts | Price in / cached / out | Price source | Priced | Good for | Measured | Seen |
|---|---|---|---|---|---|---|---|---|
| claude | quill-2-5 | low, medium, high | 2 / 0.1 / 10 | s | 2031-01-05 |  |  | 2031-01-05 |
| claude | quill-2-mini | low, medium, high | 1 / 0.1 / 5 | s | 2031-01-05 |  |  | 2031-01-05 |
| codex | zephyr-3-pro | low, medium, high | 3 / 0.3 / 15 | s | 2031-01-05 |  |  | 2031-01-05 |
| cmd | quill-2-5 | - | 2 / 0.1 / 10 | s | 2031-01-05 |  |  | 2031-01-05 |

## Picks by job

| Job | First choice | Alternatives |
|---|---|---|
| code-review | claude/quill-2-5 high | cmd/quill-2-5; ghost/none low; claude/quill-2-mini max; codex/zephyr-3-pro high |
| plan-review | claude/quill-2-5 high | claude/quill-2-mini high; codex/zephyr-3-pro high |
| build | claude/quill-2-5 medium | codex/zephyr-3-pro medium |
MD
pk() { python3 "$M" pick --matrix "$tmp/pm.md" "$@"; }
expect() { local want="$1" rc_want="$2"; shift 2; local out rc; set +e; out="$("$@" 2>"$tmp/err")"; rc=$?; set -e
  [[ $rc -eq $rc_want ]] || fail "rc $rc != $rc_want for: $*"; [[ "$out" == "$want" ]] || fail "'$out' != '$want' for: $*"; }
# code review: never the builder's own model, whichever host serves it or however it is spelled
expect "codex zephyr-3-pro high" 0 pk code-review --builder claude/quill-2-5
expect "codex zephyr-3-pro high" 0 pk code-review --builder "Quill 2.5"
expect "codex zephyr-3-pro high" 0 pk code-review --builder cmd/quill-2-5
expect "claude quill-2-5 high" 0 pk code-review --builder codex/zephyr-3-pro
expect "" 1 pk code-review --reviewer claude/quill-2-5 --builder cmd/quill-2-5
grep -q '^REFUSED: reviewer model quill-2-5 is the builder' "$tmp/err" || fail "refusal not explained"
expect "" 1 pk code-review --reviewer "Quill 2.5" --builder claude/quill-2-5
expect "OK: codex/zephyr-3-pro may review" 0 pk code-review --reviewer codex/zephyr-3-pro --builder claude/quill-2-5
expect "OK: claude/quill-2-mini may review" 0 pk code-review --reviewer claude/quill-2-mini --builder claude/quill-2-5
expect "" 64 pk code-review
# candidates missing from the matrix or with an unsupported effort are skipped, with the reason
expect "codex zephyr-3-pro high" 0 pk code-review --builder claude/quill-2-5
grep -q 'skip ghost/none low: not in the matrix' "$tmp/err" && grep -q 'skip claude/quill-2-mini max: effort max not supported' "$tmp/err" || fail "skip reasons missing: $(cat "$tmp/err")"
# plan review: a different CLI than the author's
expect "codex zephyr-3-pro high" 0 pk plan-review --author claude
expect "claude quill-2-5 high" 0 pk plan-review --author codex
expect "codex zephyr-3-pro high" 0 pk plan-review --author claude/quill-2-mini
expect "" 1 pk plan-review --author claude --reviewer claude/quill-2-mini
grep -q '^REFUSED: reviewer CLI claude is the plan author' "$tmp/err" || fail "plan-review refusal not explained"
# the builder and a --reviewer resolve against the matrix: id forms, dated ids and aliases cannot slip past
expect "codex zephyr-3-pro high" 0 pk code-review --builder 'quill-2-5[1m]'
expect "codex zephyr-3-pro high" 0 pk code-review --builder 'claude/quill-2-5[1m]'
expect "codex zephyr-3-pro high" 0 pk code-review --builder claude/quill-2-5-20311001
expect "" 1 pk code-review --reviewer 'quill-2-5[1m]' --builder claude/quill-2-5
grep -q '^REFUSED: reviewer model quill-2-5 is the builder' "$tmp/err" || fail "[1m] reviewer not refused: $(cat "$tmp/err")"
expect "" 1 pk code-review --reviewer claude/quill-2-5-20311001 --builder claude/quill-2-5
expect "" 64 pk code-review --builder ghost-9
grep -q "^--builder 'ghost-9' is not in the matrix; name it as host/model" "$tmp/err" || fail "unresolved builder not explained: $(cat "$tmp/err")"
expect "" 64 pk code-review --builder claude/ghost-9
expect "" 64 pk code-review --reviewer ghost-9 --builder claude/quill-2-5
cat > "$tmp/pa.md" <<'MD'
# Alias fixture

## Matrix

| Host | Model | Efforts | Price in / cached / out | Price source | Priced | Good for | Measured | Seen |
|---|---|---|---|---|---|---|---|---|
| claude | claude-opus-5-5 | low, high | 4 / 0.2 / 20 | s | 2031-01-05 |  |  | 2031-01-05 |
| claude | claude-sonnet-5-5 | low, high | 2 / 0.1 / 10 | s | 2031-01-05 |  |  | 2031-01-05 |
| codex | zephyr-3-pro | low, high | 3 / 0.3 / 15 | s | 2031-01-05 |  |  | 2031-01-05 |

## Picks by job

| Job | First choice | Alternatives |
|---|---|---|
| code-review | claude/claude-opus-5-5 high | claude/claude-sonnet-5-5 high; codex/zephyr-3-pro high |
MD
pa() { python3 "$M" pick --matrix "$tmp/pa.md" "$@"; }
expect "claude claude-sonnet-5-5 high" 0 pa code-review --builder opus
expect "claude claude-opus-5-5 high" 0 pa code-review --builder sonnet
expect "claude claude-sonnet-5-5 high" 0 pa code-review --builder 'claude-opus-5-5[1m]'
expect "claude claude-sonnet-5-5 high" 0 pa code-review --builder claude/claude-opus-5-5-20261001
expect "" 1 pa code-review --reviewer opus --builder claude/claude-opus-5-5
expect "" 64 pa code-review --builder haiku
# plan review: a bare --reviewer model resolves to its CLI, and an unknown one is refused
expect "" 1 pk plan-review --author claude --reviewer quill-2-mini
grep -q '^REFUSED: reviewer CLI claude is the plan author' "$tmp/err" || fail "bare reviewer model not refused: $(cat "$tmp/err")"
expect "OK: zephyr-3-pro may review" 0 pk plan-review --author claude --reviewer zephyr-3-pro
expect "" 1 pk plan-review --author claude --reviewer ghost-9
grep -q "^REFUSED: --reviewer 'ghost-9' is not in the matrix" "$tmp/err" || fail "unknown plan reviewer not refused: $(cat "$tmp/err")"
expect "OK: quill-2-5 may review" 0 pk plan-review --author codex --reviewer quill-2-5
expect "" 64 pk plan-review
expect "" 64 pk plan-review --author Opus
expect "claude quill-2-5 medium" 0 pk build
expect "" 64 pk nojob
# every candidate refused -> exit 1, no invented model
sed -i 's#^| plan-review .*#| plan-review | claude/quill-2-5 high | claude/quill-2-mini high |#' "$tmp/pm.md"
expect "" 1 pk plan-review --author claude

# --- 6b. a CLI unreachable at the first rebuild joins the picks when a later rebuild finds it -----
rm -rf "$tmp/h2"; mkdir -p "$tmp/h2"; fx2="$tmp/fx2"; mkdir -p "$fx2"
cat > "$fx2/codex-models-cache.json" <<'J'
{"fetched_at":"2031-01-04T08:00:00Z","models":[{"slug":"gpt-6.1-sol","visibility":"list",
 "supported_reasoning_levels":[{"effort":"medium"},{"effort":"high"}]}]}
J
cp "$tmp/claude-help.txt.off" "$fx2/claude-help.txt"
printf 'claude-opus-5-5\nclaude-sonnet-5-5\nclaude-haiku-5-5\n' > "$tmp/claude-real.txt"
m2="$tmp/h2/models.md"
set +e
ORCH_MODELS_FIXTURE_DIR="$fx2" python3 "$M" rebuild --out "$m2" --plan codex=P --plan claude=P > "$tmp/c1.out" 2>&1
set -e
grep -q '^UNREACHABLE claude:' "$tmp/c1.out" || fail "first rebuild should leave claude unreachable: $(cat "$tmp/c1.out")"
grep -q '^| bulk |' "$m2" && fail "bulk should have no pick before the claude rebuild"
grep -q '^| code-review | codex/gpt-6.1-sol high |  |$' "$m2" || fail "first-rebuild picks: $(grep -A8 'Picks by job' "$m2")"
set +e; python3 "$M" pick --matrix "$m2" code-review --builder codex/gpt-6.1-sol 2>/dev/null; rc=$?; set -e
[[ $rc -eq 1 ]] || fail "before the claude rebuild no reviewer exists, got rc $rc"
set +e
ORCH_MODELS_FIXTURE_DIR="$fx2" python3 "$M" rebuild --out "$m2" --claude-models "$tmp/claude-real.txt" > "$tmp/c2.out" 2>&1
set -e
grep -q '^PICK ADDED code-review: claude/claude-opus-5-5 high (now installed)$' "$tmp/c2.out" || fail "pick catch-up not reported: $(cat "$tmp/c2.out")"
grep -q '^| code-review | codex/gpt-6.1-sol high | claude/claude-opus-5-5 high; claude/claude-sonnet-5-5 high |$' "$m2" \
  || fail "claude candidates not appended, or First choice touched: $(grep '^| code-review' "$m2")"
grep -q '^| plan-review | codex/gpt-6.1-sol high | claude/claude-opus-5-5 high; claude/claude-sonnet-5-5 high |$' "$m2" || fail "plan-review picks: $(grep '^| plan-review' "$m2")"
grep -q '^| bulk | claude/claude-haiku-5-5 low |  |$' "$m2" || fail "a job with no pick was not created from the new model: $(grep '^| bulk' "$m2" || echo none)"
out="$(python3 "$M" pick --matrix "$m2" code-review --builder codex/gpt-6.1-sol 2>/dev/null)"
[[ "$out" == "claude claude-opus-5-5 high" ]] || fail "pick after the catch-up: $out"
cp "$m2" "$tmp/m2.once"
ORCH_MODELS_FIXTURE_DIR="$fx2" python3 "$M" rebuild --out "$m2" --claude-models "$tmp/claude-real.txt" > "$tmp/c3.out" 2>&1 || true
cmp -s "$m2" "$tmp/m2.once" || fail "a second rebuild changed the picks again"
grep -q '^PICK ADDED' "$tmp/c3.out" && fail "a second rebuild re-reported an added pick"

# --- 7. the shipped matrix: generic, parseable, stable under a rebuild's writer ----------------
sh="$repo_root/skills/orch/references/models.md"
python3 -I - "$M" "$sh" <<'P' || fail "shipped matrix"
import importlib.util, sys
spec = importlib.util.spec_from_file_location("om", sys.argv[1]); om = importlib.util.module_from_spec(spec); spec.loader.exec_module(om)
text = open(sys.argv[2]).read()
st = om.parse(text)
assert om.render(st) == text, "shipped matrix is not in the writer's own format"
assert len(st["rows"]) >= 10 and {"plan-review", "build", "code-review", "research", "bulk"} <= {p["job"] for p in st["picks"]}
for r in st["rows"]:
    assert r["source"] not in ("", "none") and r["priced"] != "-" and r["measured"] == "", r
    for pick in st["picks"]:
        for c in om.cands(pick, set(om.HOSTS)):
            assert om.cand_problem(c, st["rows"]) is None, (pick["job"], c)
P
grep -qiE 'owner|measured here|\(max\)|\(plus\)|laptop|mkamran' "$sh" && fail "shipped matrix has owner-specific text"
nohome="$tmp/nohome"; mkdir -p "$nohome"
out="$(HOME="$nohome" python3 "$M" path)"; [[ "$out" == "$repo_root/skills/orch/references/models.md (shipped)" ]] || fail "no user file should fall back to shipped: $out"
out="$(HOME="$nohome" python3 "$M" pick code-review --builder claude/claude-sonnet-5-5)"; [[ "$out" == "claude claude-opus-5-5 high" ]] || fail "shipped code-review pick: $out"
out="$(HOME="$nohome" python3 "$M" pick code-review --builder claude/claude-opus-5-5 2>/dev/null)"; [[ "$out" == "codex gpt-6.1-sol high" ]] || fail "shipped code-review pick for an Opus builder: $out"
out="$(HOME="$nohome" python3 "$M" show --host codex | wc -l)"; [[ "$out" -le 8 ]] || fail "show --host is not compact: $out lines"

# --- 8. SKILL.md points at the matrix and stays short ---------------------------------------
grep -q 'orch-models.py pick' "$repo_root/skills/orch/SKILL.md" || fail "SKILL.md does not point at the matrix"
[[ "$(wc -l < "$repo_root/skills/orch/SKILL.md")" -lt 150 ]] || fail "SKILL.md is 150 lines or more"
echo "orch-models tests: pass"
