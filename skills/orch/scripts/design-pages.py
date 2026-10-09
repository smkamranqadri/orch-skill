#!/usr/bin/env python3
"""design-pages: the two local HTML pages of a design round, built from exported PNGs.

  design-pages.py review <dir>       <dir>/review.json  -> <dir>/review.html
  design-pages.py prototype <dir>    <dir>/inventory.json + <dir>/links.json -> <dir>/prototype.html
  design-pages.py check <dir> [--previous <dir>]
                                     report missing images, dangling links, hotspots off the frame,
                                     and frames the previous round's inventory had that are gone

Both pages are plain files that open from disk; images are referenced by relative path, nothing
is uploaded. Open them with `open <dir>/review.html`. `prototype.html?hot#<frame>` opens a frame
with its hotspots drawn, which is how an agent proves their placement from a headless screenshot.

review.json
  {"title": "...", "round": 2, "intro": "one or two sentences",
   "review_first": ["03", "05"],                         # ids to look at first
   "screens": [{"id": "03", "title": "Space · described", "what": "one sentence: what changed and why",
                "feedback": "the user's earlier words on this screen, or null",
                "before": {"desktop": "exports/x.png", "phone": "exports/y.png"},    # any may be null
                "after":  {"desktop": "exports/x2.png", "phone": "exports/y2.png"},
                "status": "changed" | "new" | "unchanged"}]}
  The user answers in chat by id: "03 approved", "05 needs change: ...".

inventory.json   (Pencil's frame list, as exported by the design agent)
  [{"id": "QNVpF", "name": "Desktop 1280 · before", "width": 1280, "height": 1515,
    "image": "exports/QNVpF.png", "group": "desktop" | "phone", "start": true}]
  `image` defaults to exports/<id>.png; `group` defaults from the name (phone when it says Phone or
  the width is under 500); exactly one frame should carry `start`, else the first is used.

links.json       (hotspots: what is clickable where, in frame pixels)
  [{"from": "QNVpF", "rect": [x, y, w, h], "to": "b8eo5", "label": "Add a description"}]
  The design agent takes rects from the frame's button and link bounds (Pencil Get with bounds,
  relative to the frame). Hotspots are drawn in percentages, so the page scales to any width.
"""
import html
import json
import os
import struct
import sys

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1a1a1a;--muted:#6b6b6b;--line:#e3e1dc;--accent:#0b6b5a;--warn:#b35c00}
@media(prefers-color-scheme:dark){:root{--bg:#141414;--card:#1e1e1e;--ink:#eee;--muted:#9a9a9a;--line:#333;--accent:#5ad1b8;--warn:#f0a35a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,Inter,system-ui,sans-serif}
a{color:var(--accent)}header{padding:20px 16px 8px;max-width:1400px;margin:0 auto}h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:0}
.muted{color:var(--muted)}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 9px;font-size:12px;margin-left:6px;color:var(--muted)}
.pill.changed{border-color:var(--warn);color:var(--warn)}.pill.new{border-color:var(--accent);color:var(--accent)}
main{max-width:1400px;margin:0 auto;padding:0 16px 40px}
.first{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:12px 0 20px}
section.screen{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 18px}
section.screen .head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.id{font-weight:700;font-variant-numeric:tabular-nums}
.fb{border-left:3px solid var(--warn);padding:6px 10px;margin:10px 0;background:color-mix(in srgb,var(--warn) 8%,transparent);white-space:pre-wrap}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}@media(max-width:800px){.pair{grid-template-columns:1fr}}
.col h3{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 6px}
.shots{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap}.shots a{display:block;flex:1 1 220px}
.shots a.phone{flex:0 0 160px}.shots img{width:100%;height:auto;border:1px solid var(--line);border-radius:6px;background:#fff;display:block}
.missing{border:1px dashed var(--warn);color:var(--warn);padding:18px;border-radius:6px;font-size:13px}
/* prototype */
.proto{display:grid;grid-template-columns:260px 1fr;min-height:100vh}@media(max-width:800px){.proto{grid-template-columns:1fr}}
.proto nav{border-right:1px solid var(--line);padding:12px;overflow:auto;max-height:100vh;position:sticky;top:0}
.proto nav h1{font-size:16px}.proto nav button{display:block;width:100%;text-align:left;background:none;border:0;color:var(--ink);padding:5px 6px;border-radius:6px;cursor:pointer;font:inherit}
.proto nav button.on{background:color-mix(in srgb,var(--accent) 15%,transparent)}.proto nav .g{margin:10px 0 2px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.stage{padding:14px 16px}.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
.bar button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:4px 10px;cursor:pointer}
.frame{position:relative;display:inline-block;max-width:100%;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:#fff}
.frame img{display:block;max-width:100%;height:auto}
.hot{position:absolute;display:block;border-radius:4px;cursor:pointer}
.show .hot{outline:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 18%,transparent)}
.frame.phone{max-width:390px}
"""


def png_size(path):
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24])
            return w, h
    except OSError:
        pass
    return None


def load(d, name):
    with open(os.path.join(d, name)) as f:
        return json.load(f)


def esc(s):
    return html.escape("" if s is None else str(s))


def shot(d, rel, cls, alt):
    if not rel:
        return ""
    if not os.path.exists(os.path.join(d, rel)):
        return f'<div class="missing {cls}">missing: {esc(rel)}</div>'
    return f'<a class="{cls}" href="{esc(rel)}" target="_blank"><img loading="lazy" src="{esc(rel)}" alt="{esc(alt)}"></a>'


def build_review(d):
    r = load(d, "review.json")
    screens = r.get("screens", [])
    out = [f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>{esc(r.get('title', 'Design review'))}</title><style>{CSS}</style></head><body>"]
    out.append(f"<header><h1>{esc(r.get('title', 'Design review'))}"
               + (f" <span class=pill>round {esc(r['round'])}</span>" if r.get("round") else "") + "</h1>")
    if r.get("intro"):
        out.append(f"<p class=muted>{esc(r['intro'])}</p>")
    out.append("<p class=muted>Answer by id: <b>03 approved</b>, or <b>05 needs change: …</b>. Click an image to open it full size.</p></header><main>")
    first = r.get("review_first") or []
    if first:
        titles = {s["id"]: s.get("title", "") for s in screens}
        out.append("<div class=first><b>Review these first:</b> " + ", ".join(
            f'<a href="#s{esc(i)}">{esc(i)} {esc(titles.get(i, ""))}</a>' for i in first) + "</div>")
    for s in screens:
        st = s.get("status", "changed")
        out.append(f'<section class=screen id="s{esc(s["id"])}"><div class=head><span class=id>{esc(s["id"])}</span>'
                   f'<h2>{esc(s.get("title", ""))}</h2><span class="pill {esc(st)}">{esc(st)}</span></div>')
        if s.get("what"):
            out.append(f"<p>{esc(s['what'])}</p>")
        if s.get("feedback"):
            out.append(f"<div class=fb><b>Your feedback:</b> {esc(s['feedback'])}</div>")
        out.append("<div class=pair>")
        for col, label in (("before", "Before"), ("after", "After")):
            v = s.get(col) or {}
            out.append(f"<div class=col><h3>{label}</h3><div class=shots>"
                       + shot(d, v.get("desktop"), "desktop", f"{s.get('title', '')} {label} desktop")
                       + shot(d, v.get("phone"), "phone", f"{s.get('title', '')} {label} phone")
                       + ("<div class=muted>none</div>" if not v.get("desktop") and not v.get("phone") else "")
                       + "</div></div>")
        out.append("</div></section>")
    out.append("</main></body></html>")
    path = os.path.join(d, "review.html")
    with open(path, "w") as f:
        f.write("\n".join(out))
    return path, len(screens)


def norm_frames(d, inv):
    frames = []
    for fr in inv:
        f = dict(fr)
        f.setdefault("image", f"exports/{f['id']}.png")
        name = f.get("name", "")
        if "group" not in f:
            f["group"] = "phone" if ("phone" in name.lower() or int(f.get("width") or 9999) < 500) else "desktop"
        size = png_size(os.path.join(d, f["image"]))
        f["exists"] = size is not None
        if size and not f.get("width"):
            f["width"], f["height"] = size
        frames.append(f)
    return frames


def build_prototype(d):
    frames = norm_frames(d, load(d, "inventory.json"))
    links = load(d, "links.json") if os.path.exists(os.path.join(d, "links.json")) else []
    by_id = {f["id"]: f for f in frames}
    start = next((f["id"] for f in frames if f.get("start")), frames[0]["id"] if frames else "")
    hot = {}
    for l in links:
        fr = by_id.get(l["from"])
        if not fr or not fr.get("width"):
            continue
        x, y, w, h = l["rect"]
        W, H = float(fr["width"]), float(fr["height"])
        hot.setdefault(l["from"], []).append({
            "to": l["to"], "label": l.get("label", ""),
            "l": round(100 * x / W, 3), "t": round(100 * y / H, 3), "w": round(100 * w / W, 3), "h": round(100 * h / H, 3)})
    data = {"start": start, "frames": [{"id": f["id"], "name": f.get("name", f["id"]), "group": f["group"],
                                         "image": f["image"], "exists": f["exists"], "hot": hot.get(f["id"], [])} for f in frames]}
    title = os.path.basename(os.path.abspath(d))
    page = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Prototype · {esc(title)}</title><style>{CSS}</style></head><body><div class=proto>
<nav><h1>Prototype</h1><p class=muted style="font-size:12px">Click inside a screen to follow a link. <b>?</b> shows the hotspots, <b>←</b> goes back.</p><div id=list></div></nav>
<div class=stage><div class=bar><button id=back>← back</button><button id=toggle>? hotspots</button><span id=title class=muted></span></div>
<div id=frame class=frame></div></div></div>
<script>
const DATA = {json.dumps(data)};
const byId = Object.fromEntries(DATA.frames.map(f => [f.id, f]));
const hist = [];
let cur = location.hash.slice(1) || DATA.start, show = location.search.includes('hot');
function render() {{
  const f = byId[cur] || DATA.frames[0]; if (!f) return;
  document.getElementById('title').textContent = f.name + (f.hot.length ? ' · ' + f.hot.length + ' link' + (f.hot.length > 1 ? 's' : '') : ' · no links');
  const box = document.getElementById('frame'); box.className = 'frame ' + f.group + (show ? ' show' : '');
  box.innerHTML = f.exists ? `<img src="${{f.image}}" alt="${{f.name}}">` : `<div class=missing>missing image: ${{f.image}}</div>`;
  for (const h of f.hot) {{
    const a = document.createElement('a'); a.className = 'hot'; a.title = h.label || h.to; a.href = '#' + h.to;
    a.style.cssText = `left:${{h.l}}%;top:${{h.t}}%;width:${{h.w}}%;height:${{h.h}}%`;
    a.onclick = e => {{ e.preventDefault(); go(h.to); }}; box.appendChild(a);
  }}
  for (const b of document.querySelectorAll('nav button')) b.classList.toggle('on', b.dataset.id === f.id);
  history.replaceState(null, '', '#' + f.id);
}}
function go(id) {{ if (!byId[id]) return; hist.push(cur); cur = id; render(); }}
const list = document.getElementById('list');
for (const g of ['desktop', 'phone']) {{
  const fs = DATA.frames.filter(f => f.group === g); if (!fs.length) continue;
  const h = document.createElement('div'); h.className = 'g'; h.textContent = g; list.appendChild(h);
  for (const f of fs) {{ const b = document.createElement('button'); b.dataset.id = f.id; b.textContent = f.name; b.onclick = () => go(f.id); list.appendChild(b); }}
}}
document.getElementById('back').onclick = () => {{ if (hist.length) {{ cur = hist.pop(); render(); }} }};
document.getElementById('toggle').onclick = () => {{ show = !show; render(); }};
addEventListener('keydown', e => {{ if (e.key === '?') {{ show = !show; render(); }} if (e.key === 'ArrowLeft' || e.key === 'Backspace') document.getElementById('back').click(); }});
addEventListener('hashchange', () => {{ const id = location.hash.slice(1); if (byId[id] && id !== cur) {{ hist.push(cur); cur = id; render(); }} }});
render();
</script></body></html>"""
    path = os.path.join(d, "prototype.html")
    with open(path, "w") as f:
        f.write(page)
    return path, len(frames), sum(len(v) for v in hot.values())


def check(d, previous=None):
    problems = []
    if os.path.exists(os.path.join(d, "inventory.json")):
        frames = norm_frames(d, load(d, "inventory.json"))
        ids = {f["id"] for f in frames}
        if previous and os.path.exists(os.path.join(previous, "inventory.json")):
            for f in load(previous, "inventory.json"):
                if f["id"] not in ids:
                    problems.append(f"frame {f['id']} ({f.get('name', '')}) was in the previous round and is gone: the prototype no longer reaches it")
        for f in frames:
            if not f["exists"]:
                problems.append(f"frame {f['id']}: image missing: {f['image']}")
        if sum(1 for f in frames if f.get("start")) > 1:
            problems.append("more than one frame marked start")
        if os.path.exists(os.path.join(d, "links.json")):
            by = {f["id"]: f for f in frames}
            for i, l in enumerate(load(d, "links.json")):
                if l.get("from") not in ids:
                    problems.append(f"link {i}: from {l.get('from')} is not a frame")
                    continue
                if l.get("to") not in ids:
                    problems.append(f"link {i}: to {l.get('to')} is not a frame")
                fr = by[l["from"]]
                x, y, w, h = l.get("rect", [0, 0, 0, 0])
                if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > fr["width"] or y + h > fr["height"]:
                    problems.append(f"link {i}: rect {l.get('rect')} is off frame {l['from']} ({fr['width']}×{fr['height']})")
    else:
        problems.append("no inventory.json")
    if os.path.exists(os.path.join(d, "review.json")):
        r = load(d, "review.json")
        ids = [s["id"] for s in r.get("screens", [])]
        if len(ids) != len(set(ids)):
            problems.append("review: duplicate screen ids")
        for i in r.get("review_first") or []:
            if i not in ids:
                problems.append(f"review: review_first id {i} is not a screen")
        for s in r.get("screens", []):
            for col in ("before", "after"):
                for k, rel in (s.get(col) or {}).items():
                    if rel and not os.path.exists(os.path.join(d, rel)):
                        problems.append(f"review {s['id']}: {col} {k} image missing: {rel}")
            if not s.get("what"):
                problems.append(f"review {s['id']}: no sentence on what changed and why")
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    cmd, d = argv[0], argv[1]
    if cmd == "review":
        p, n = build_review(d); print(f"wrote {p} ({n} screens)"); return 0
    if cmd == "prototype":
        p, n, h = build_prototype(d); print(f"wrote {p} ({n} frames, {h} hotspots)"); return 0
    if cmd == "check":
        prev = argv[argv.index("--previous") + 1] if "--previous" in argv else None
        ps = check(d, prev)
        print("\n".join(ps) if ps else "ok"); return 1 if ps else 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
