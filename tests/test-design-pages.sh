#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$repo_root/skills/orch/scripts/design-pages.py"
tmp="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
d="$tmp/round"; mkdir -p "$d/exports"
# two tiny real PNGs (1x1) so sizes come from the inventory, one missing image on purpose
png() { printf '\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde' > "$1"; }
png "$d/exports/A.png"; png "$d/exports/B.png"; png "$d/exports/P.png"
cat > "$d/inventory.json" <<'J'
[{"id":"A","name":"Desktop · home","width":1000,"height":500,"start":true},
 {"id":"B","name":"Desktop · detail","width":1000,"height":500},
 {"id":"P","name":"Phone · home","width":390,"height":844},
 {"id":"M","name":"Desktop · missing","width":1000,"height":500}]
J
cat > "$d/links.json" <<'J'
[{"from":"A","rect":[100,50,200,25],"to":"B","label":"Open"},
 {"from":"B","rect":[0,0,1000,500],"to":"A","label":"Back"},
 {"from":"P","rect":[0,772,390,72],"to":"A","label":"Tab"}]
J
cat > "$d/review.json" <<'J'
{"title":"T","round":1,"review_first":["02"],"screens":[
 {"id":"01","title":"Home","status":"changed","what":"Moved the action.","feedback":"01 needs change: hidden","before":{"desktop":"exports/A.png","phone":"exports/P.png"},"after":{"desktop":"exports/B.png","phone":null}},
 {"id":"02","title":"Detail","status":"new","what":"New dialog.","feedback":null,"before":{},"after":{"desktop":"exports/B.png","phone":"exports/P.png"}}]}
J
# check reports the missing image and nothing else
set +e; out="$(python3 "$S" check "$d")"; rc=$?; set -e
[[ $rc -eq 1 ]] || fail "check should exit 1 with a missing image"
[[ "$out" == "frame M: image missing: exports/M.png" ]] || fail "check output: $out"

# prototype: hotspots in percentages of the frame, start frame, groups
python3 "$S" prototype "$d" >/dev/null
test -f "$d/prototype.html" || fail "prototype not written"
grep -q '"start": "A"' "$d/prototype.html" || fail "start frame"
grep -q '"l": 10.0, "t": 10.0, "w": 20.0, "h": 5.0' "$d/prototype.html" || fail "hotspot percentages wrong"
grep -q '"group": "phone"' "$d/prototype.html" || fail "phone group from name"
grep -q '"exists": false' "$d/prototype.html" || fail "missing image not flagged in data"
grep -q 'exports/A.png' "$d/prototype.html" || fail "image paths relative"

# review: ids, feedback block, review-first link, missing after-phone handled as none
python3 "$S" review "$d" >/dev/null
test -f "$d/review.html" || fail "review not written"
grep -q 'id="s01"' "$d/review.html" && grep -q 'id="s02"' "$d/review.html" || fail "screen anchors"
grep -q 'Your feedback:</b> 01 needs change: hidden' "$d/review.html" || fail "feedback block"
grep -q 'href="#s02">02 Detail' "$d/review.html" || fail "review-first link"
grep -q 'class="pill new"' "$d/review.html" || fail "status pill"
grep -q 'src="exports/P.png"' "$d/review.html" || fail "phone image"

# check catches dangling links, off-frame rects and a review screen without its sentence
cat > "$d/links.json" <<'J'
[{"from":"A","rect":[900,450,200,100],"to":"B"},{"from":"A","rect":[0,0,10,10],"to":"ZZ"},{"from":"QQ","rect":[0,0,1,1],"to":"A"}]
J
python3 - "$d/review.json" <<'P'
import json,sys; p=sys.argv[1]; r=json.load(open(p)); r["screens"][1]["what"]=""; json.dump(r,open(p,"w"))
P
set +e; out="$(python3 "$S" check "$d")"; set -e
grep -q "link 0: rect .* is off frame A" <<<"$out" || fail "off-frame rect not caught: $out"
grep -q "link 1: to ZZ is not a frame" <<<"$out" || fail "dangling to not caught"
grep -q "link 2: from QQ is not a frame" <<<"$out" || fail "dangling from not caught"
grep -q "review 02: no sentence" <<<"$out" || fail "missing sentence not caught"

# --previous names a frame that was reachable last round and is gone now
prev="$tmp/prev"; mkdir -p "$prev"
echo '[{"id":"A","name":"Desktop · home","width":1000,"height":500},{"id":"OLD","name":"Desktop · gone","width":1000,"height":500}]' > "$prev/inventory.json"
set +e; out="$(python3 "$S" check "$d" --previous "$prev")"; set -e
grep -q "frame OLD (Desktop · gone) was in the previous round and is gone" <<<"$out" || fail "gone frame not caught: $out"
echo "design-pages tests: pass"
