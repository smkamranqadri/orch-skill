#!/usr/bin/env python3
"""The orch model matrix: discover, merge, show and pick. Standard library only.

  orch-models.py path                       which matrix orch reads (user's, else shipped)
  orch-models.py show [--host H] [--unpriced]   compact rows, never the whole file
  orch-models.py discover [--claude-models F]   what the installed CLIs offer, as JSON
  orch-models.py rebuild [--plan host=NAME]... [--prices F] [--claude-models F]
                                            discover, merge into the user's matrix, report
  orch-models.py pick <job> [--builder X] [--author X] [--reviewer X]
                                            harness, model and effort for a job, rules applied

The user's matrix is ~/.agents/orch/models.md (ORCH_MODELS_FILE overrides); an orch update never
touches it. Without one, orch reads the shipped references/models.md. A rebuild keeps the user's
"Good for" and "Measured" cells, the picks, free sections and plans, and never guesses: a CLI or
price source it could not reach, and a model with no sourced price, are reported and exit 3.
Tests set ORCH_MODELS_FIXTURE_DIR (codex-models-cache.json, cmd-list-models.txt, agy-models.txt,
claude-help.txt; an absent file means the CLI is not installed) and ORCH_MODELS_TODAY.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOSTS = ["claude", "codex", "agy", "cmd"]
EFFORT_ORDER = ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"]
COLS = ["Host", "Model", "Efforts", "Price in / cached / out", "Price source", "Priced",
        "Good for", "Measured", "Seen"]
PICK_COLS = ["Job", "First choice", "Alternatives"]
KNOWN = ["Plans", "Matrix", "Picks by job", "Sources"]
CODE_REVIEW, PLAN_REVIEW = "code-review", "plan-review"
SHIPPED = Path(__file__).resolve().parent.parent / "references" / "models.md"


def today():
    return os.environ.get("ORCH_MODELS_TODAY") or datetime.date.today().isoformat()


def user_file():
    env = os.environ.get("ORCH_MODELS_FILE")
    return Path(env) if env else Path.home() / ".agents" / "orch" / "models.md"


def active_file(override=None):
    if override:
        return Path(override), "given"
    u = user_file()
    return (u, "user") if u.is_file() else (SHIPPED, "shipped")


# ---------------------------------------------------------------- the matrix file

def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [c.replace("\\|", "|").strip() for c in cells[1:-1]]


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def table(lines, cols):
    out, seen_header = [], False
    for ln in lines:
        if not ln.lstrip().startswith("|"):
            continue
        cells = split_row(ln)
        if not seen_header:
            seen_header = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        cells += [""] * (len(cols) - len(cells))
        out.append(dict(zip(cols, cells[:len(cols)])))
    return out


def parse(text):
    parts = re.split(r"(?m)^(?=## )", text)
    head = parts[0].rstrip("\n")
    sections, order = {}, []
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        name = title[3:].strip()
        sections[name] = body.strip("\n")
        order.append(name)
    plans = {}
    for ln in sections.get("Plans", "").splitlines():
        m = re.match(r"-\s*([^:]+):\s*(.+)$", ln)
        if m:
            plans[m.group(1).strip()] = m.group(2).strip()
    rows = [{"host": r["Host"], "model": r["Model"],
             "efforts": [e.strip() for e in r["Efforts"].split(",") if e.strip() and e.strip() != "-"],
             "price": r["Price in / cached / out"], "source": r["Price source"], "priced": r["Priced"],
             "good": r["Good for"], "measured": r["Measured"], "seen": r["Seen"]}
            for r in table(sections.get("Matrix", "").splitlines(), COLS) if r["Host"] and r["Model"]]
    picks = [{"job": r["Job"], "first": r["First choice"], "alts": r["Alternatives"]}
             for r in table(sections.get("Picks by job", "").splitlines(), PICK_COLS) if r["Job"]]
    other = [(n, sections[n]) for n in order if n not in KNOWN]
    return {"head": head, "plans": plans, "rows": rows, "picks": picks, "other": other}


def host_rank(h):
    return HOSTS.index(h) if h in HOSTS else len(HOSTS)


def render(st):
    out = [st["head"], ""]
    out += ["## Plans", ""]
    out += [f"- {h}: {p}" for h, p in sorted(st["plans"].items(), key=lambda kv: (host_rank(kv[0]), kv[0]))] \
        or ["- none recorded"]
    out += ["", "## Matrix", "", "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    rows = sorted(st["rows"], key=lambda r: host_rank(r["host"]))
    for r in rows:
        vals = [r["host"], r["model"], ", ".join(r["efforts"]) or "-", r["price"], r["source"],
                r["priced"], r["good"], r["measured"], r["seen"]]
        out.append("| " + " | ".join(cell(v) for v in vals) + " |")
    out += ["", "## Picks by job", "", "| " + " | ".join(PICK_COLS) + " |", "|" + "---|" * len(PICK_COLS)]
    for p in st["picks"]:
        out.append("| " + " | ".join(cell(v) for v in (p["job"], p["first"], p["alts"])) + " |")
    for name, body in st["other"]:
        out += ["", f"## {name}", ""] + ([body] if body.strip() else [])
    srcs = sorted({r["source"] for r in rows if r["source"] and r["source"] != "none"})
    out += ["", "## Sources", ""] + ([f"- {s}" for s in srcs] or ["- none"])
    return "\n".join(out).rstrip("\n") + "\n"


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- discovery

def run_cmd(argv):
    if not shutil.which(argv[0]):
        return None, "not installed"
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return None, f"`{' '.join(argv)}` timed out after 30 s"
    except OSError as e:
        return None, f"`{' '.join(argv)}` failed: {e}"
    if p.returncode != 0:
        first = (p.stderr.strip().splitlines() or ["no output"])[0][:120]
        return None, f"`{' '.join(argv)}` exited {p.returncode}: {first}"
    return p.stdout, None


def source_text(fixture_name, argv=None, path=None):
    """(text, error). A fixture dir replaces both the CLI and the cache file."""
    fx = os.environ.get("ORCH_MODELS_FIXTURE_DIR")
    if fx:
        f = Path(fx) / fixture_name
        return (f.read_text(), None) if f.is_file() else (None, "not installed")
    if path is not None:
        if not shutil.which(argv[0] if argv else "codex"):
            return None, "not installed"
        if not path.is_file():
            return None, f"{path} is missing; start the CLI once so it writes it"
        return path.read_text(), None
    return run_cmd(argv)


def order_efforts(es):
    return sorted(set(es), key=lambda e: EFFORT_ORDER.index(e) if e in EFFORT_ORDER else 99)


def discover_codex():
    text, err = source_text("codex-models-cache.json", ["codex"], Path.home() / ".codex" / "models_cache.json")
    if err:
        return {"error": err}
    try:
        data = json.loads(text)
        models = []
        for m in data["models"]:
            if m.get("visibility", "list") != "list":
                continue
            efforts = [e["effort"] for e in m.get("supported_reasoning_levels", [])]
            models.append({"id": m["slug"], "efforts": efforts})
    except (ValueError, KeyError, TypeError) as e:
        return {"error": f"models_cache.json unreadable ({type(e).__name__}: {e})"}
    if not models:
        return {"error": "models_cache.json lists no visible models"}
    return {"models": models, "source": f"models_cache.json fetched {str(data.get('fetched_at', 'unknown'))[:10]}"}


def discover_cmd():
    text, err = source_text("cmd-list-models.txt", ["cmd", "--list-models"])
    if err:
        return {"error": err}
    models, section = [], ""
    declared = re.search(r"(\d+) models", text)
    for ln in text.splitlines():
        if ln and not ln[0].isspace() and not re.match(r"\S+\s{2,}\S", ln):
            section = ln.strip()
            continue
        m = re.match(r"^([a-z0-9][a-z0-9._:/-]*)\s{2,}\S", ln)
        if not m or m.group(1).endswith(":") or "headless" in section.lower():
            continue
        models.append({"id": m.group(1), "efforts": []})
    if not models:
        return {"error": "`cmd --list-models` printed no model lines"}
    if declared and int(declared.group(1)) != len(models):
        return {"error": f"parsed {len(models)} models but the list header says {declared.group(1)}; "
                         "the output format changed"}
    return {"models": models, "source": "cmd --list-models"}


def discover_agy():
    text, err = source_text("agy-models.txt", ["agy", "models"])
    if err:
        return {"error": err}
    by_base, order = {}, []
    for ln in text.splitlines():
        if "\t" not in ln:
            continue
        mid, name = [x.strip() for x in ln.split("\t", 1)]
        eff = re.search(r"\((minimal|low|medium|high|xhigh|max)\)\s*$", name, re.I)
        if eff and mid.lower().endswith("-" + eff.group(1).lower()):
            base, e = mid[:-(len(eff.group(1)) + 1)], eff.group(1).lower()
        else:
            base, e = mid, None
        if base not in by_base:
            by_base[base] = []
            order.append(base)
        if e:
            by_base[base].append(e)
    if not order:
        return {"error": "`agy models` printed no model lines (not signed in?)"}
    return {"models": [{"id": b, "efforts": order_efforts(by_base[b])} for b in order],
            "source": "agy models (pass <model>-<effort> to agy)"}


def discover_claude(models_file):
    text, err = source_text("claude-help.txt", ["claude", "--help"])
    if err:
        return {"error": err}
    m = re.search(r"--effort\s+<level>[^(]*\(([^)]*)\)", text)
    efforts = order_efforts([e.strip() for e in m.group(1).split(",")]) if m else []
    if not models_file:
        return {"error": "installed, but the CLI does not list model ids; pass --claude-models <file> "
                         "(one id per line, from platform.claude.com/docs/en/about-claude/models)"}
    try:
        ids = [ln.split("#")[0].strip() for ln in Path(models_file).read_text().splitlines()]
    except OSError as e:
        return {"error": f"--claude-models unreadable: {e}"}
    ids = [i for i in ids if i]
    if not ids:
        return {"error": f"--claude-models {models_file} lists no ids"}
    return {"models": [{"id": i, "efforts": efforts} for i in ids],
            "source": "claude --help (efforts) and the models file (ids)"}


def discover_all(claude_models):
    return {"claude": discover_claude(claude_models), "codex": discover_codex(),
            "agy": discover_agy(), "cmd": discover_cmd()}


# ---------------------------------------------------------------- rebuild

def fmt_num(x):
    return "-" if x is None else f"{x:g}"


def load_prices(path):
    """Returns (by_key, failed_sources, problems). A price without a source is refused."""
    data = json.loads(Path(path).read_text())
    by_key, problems = {}, []
    for p in data.get("prices", []):
        label = f"{p.get('host')}/{p.get('model')}"
        nums = [p.get("in"), p.get("out")] + ([p["cached"]] if p.get("cached") is not None else [])
        if not p.get("host") or not p.get("model"):
            problems.append(f"price entry without host and model ignored: {p}")
        elif not str(p.get("source", "")).strip():
            problems.append(f"price for {label} has no source; not recorded")
        elif any(isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0 for n in nums):
            problems.append(f"price for {label} is not a non-negative number; not recorded")
        else:
            by_key[(p["host"], p["model"])] = p
    return by_key, data.get("sources_failed", []), problems


def canon(m):
    s = m.strip().lower()
    s = s.rsplit("/", 1)[-1]
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"[\s-]*\(latest\)", "", s)
    s = re.sub(r"[\s-]*\((minimal|low|medium|high|xhigh|max)\)$", "", s)
    s = re.sub(r"\s+(minimal|low|medium|high|xhigh|max|ultra)$", "", s)
    s = re.sub(r"-(minimal|low|medium|high|xhigh)$", "", s)
    s = re.sub(r"[\s._]+", "-", s)
    s = re.sub(r"^claude-", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return re.sub(r"-\d{8}$", "", s)


CLAUDE_ALIASES = {"opus", "sonnet", "haiku", "fable"}


def resolve(ref, rows, hosts):
    """The matrix rows a name refers to: host/model, a bare model in any spelling canon folds
    (Claude Code's `[1m]` ids, dated ids), or a Claude alias (opus, sonnet, haiku, fable)."""
    host, model = split_ref(ref.strip(), hosts)
    c = canon(model)
    if not c:
        return []
    hit = [r for r in rows if host in (None, r["host"]) and canon(r["model"]) == c]
    if not hit and c in CLAUDE_ALIASES and host in (None, "claude"):
        hit = [r for r in rows if r["host"] == "claude" and canon(r["model"]).split("-")[0] == c]
    return hit


def split_ref(ref, hosts):
    """'host/model' or a bare model -> (host or None, model)."""
    head, sep, rest = ref.partition("/")
    return (head, rest) if sep and head in hosts else (None, ref)


def parse_cand(text, hosts):
    t = text.strip()
    if not t:
        return None
    ref, _, eff = t.partition(" ")
    host, model = split_ref(ref, hosts)
    return {"host": host, "model": model, "effort": eff.strip() or "-", "text": t}


def cands(pick, hosts):
    items = [pick["first"]] + [a for a in pick["alts"].split(";")]
    return [c for c in (parse_cand(i, hosts) for i in items) if c]


def cand_problem(c, rows):
    row = next((r for r in rows if r["host"] == c["host"] and r["model"] == c["model"]), None)
    if row is None:
        return "not in the matrix"
    if c["effort"] != "-" and row["efforts"] and c["effort"] not in row["efforts"]:
        return f"effort {c['effort']} not supported (has {', '.join(row['efforts'])})"
    if c["effort"] != "-" and not row["efforts"]:
        return f"effort {c['effort']} not supported (none known)"
    return None


def cmd_rebuild(a):
    dest = Path(a.out) if a.out else user_file()
    seed = parse(SHIPPED.read_text())
    if dest.is_file():
        st, fresh = parse(dest.read_text()), False
    else:
        st, fresh = {"head": seed["head"], "plans": {}, "rows": [], "picks": [], "other": seed["other"]}, True
    seed_good = {(r["host"], r["model"]): r["good"] for r in seed["rows"]}
    rows = {(r["host"], r["model"]): r for r in st["rows"]}
    today_s, report, problems, report_picks = today(), [], [], []
    prices, failed_src, price_problems = ({}, [], [])
    if a.prices:
        try:
            prices, failed_src, price_problems = load_prices(a.prices)
        except (OSError, ValueError, AttributeError) as e:
            problems.append(f"price file {a.prices} unreadable: {e}")
            failed_src = []
    problems += price_problems

    disc = discover_all(a.claude_models)
    not_installed, unreachable, kept_missing, new_keys = [], [], [], set()
    for host in HOSTS:
        d = disc[host]
        if "error" in d:
            (not_installed if d["error"] == "not installed" else unreachable).append((host, d["error"]))
            continue
        found = set()
        added = 0
        for m in d["models"]:
            key = (host, m["id"])
            found.add(key)
            if key not in rows:
                rows[key] = {"host": host, "model": m["id"], "efforts": [], "price": "unknown",
                             "source": "none", "priced": "-", "good": seed_good.get(key, ""),
                             "measured": "", "seen": "-"}
                st["rows"].append(rows[key])
                new_keys.add(key)
                added += 1
            rows[key]["efforts"] = m["efforts"]
            rows[key]["seen"] = today_s
        kept_missing += [f"{h}/{mo}" for (h, mo) in rows if h == host and (h, mo) not in found]
        report.append(f"{host}: {len(d['models'])} models, {added} new ({d['source']})")

    for (host, model), p in prices.items():
        if (host, model) not in rows:
            problems.append(f"price for {host}/{model} ignored: not in the matrix")
            continue
        r = rows[(host, model)]
        r["price"] = f"{fmt_num(p['in'])} / {fmt_num(p.get('cached'))} / {fmt_num(p['out'])}"
        r["source"], r["priced"] = str(p["source"]).strip(), str(p.get("date") or today_s)

    for spec in a.plan or []:
        h, sep, name = spec.partition("=")
        if not sep or not name.strip():
            problems.append(f"--plan {spec!r} ignored; use host=NAME")
        else:
            st["plans"][h.strip()] = name.strip()

    if fresh:
        for p in seed["picks"]:
            keep = [c for c in cands(p, set(HOSTS)) if not cand_problem(c, st["rows"])]
            if keep:
                st["picks"].append({"job": p["job"], "first": keep[0]["text"],
                                    "alts": "; ".join(c["text"] for c in keep[1:])})
            else:
                problems.append(f"no pick for job {p['job']}: none of its candidates is installed")
    else:
        hosts_all = {r["host"] for r in st["rows"]} | set(HOSTS)
        for p in st["picks"]:
            for c in cands(p, hosts_all):
                why = cand_problem(c, st["rows"])
                if why:
                    problems.append(f"pick {p['job']}: {c['text']} {why}")
        # a model first seen this run (a CLI that was unreachable at the first rebuild) joins the
        # shipped candidates for its job: appended to Alternatives, or a new job row; First choice stays
        for sp in seed["picks"]:
            mine = next((p for p in st["picks"] if p["job"] == sp["job"]), None)
            have = {(c["host"], canon(c["model"])) for c in cands(mine, hosts_all)} if mine else set()
            new = [c for c in cands(sp, set(HOSTS)) if (c["host"], c["model"]) in new_keys
                   and not cand_problem(c, st["rows"]) and (c["host"], canon(c["model"])) not in have]
            if mine is None and new:
                st["picks"].append({"job": sp["job"], "first": new[0]["text"],
                                    "alts": "; ".join(c["text"] for c in new[1:])})
            elif new:
                mine["alts"] = "; ".join([a.strip() for a in mine["alts"].split(";") if a.strip()]
                                         + [c["text"] for c in new])
            report_picks += [f"PICK ADDED {sp['job']}: {c['text']} (now installed)" for c in new]

    write_atomic(dest, render(st))

    out = [f"orch-models rebuild {today_s} -> {dest}"] + report
    if not_installed:
        out.append("not installed (skipped): " + ", ".join(h for h, _ in not_installed))
    for h, why in unreachable:
        out.append(f"UNREACHABLE {h}: {why}")
    for s in failed_src:
        out.append(f"PRICE SOURCE UNREACHABLE {s.get('source')}: {s.get('reason', 'no reason given')}")
    if kept_missing:
        out.append("not discovered this run, kept: " + ", ".join(sorted(kept_missing)))
    for h in sorted({r["host"] for r in st["rows"]}, key=host_rank):
        n = sum(1 for r in st["rows"] if r["host"] == h and r["source"] in ("", "none"))
        if n:
            out.append(f"NO PRICE SOURCE {h}: {n} models (orch-models.py show --unpriced --host {h})")
    for h in HOSTS:
        if "error" not in disc[h] and h not in st["plans"]:
            out.append(f"PLAN UNKNOWN {h}: ask the user, then rebuild with --plan {h}=NAME")
    out += report_picks
    out += [f"PROBLEM {p}" for p in problems]
    print("\n".join(out))
    bad = unreachable or failed_src or problems or any(
        l.startswith(("NO PRICE SOURCE", "PLAN UNKNOWN")) for l in out)
    return 3 if bad else 0


# ---------------------------------------------------------------- show, path, pick

def load_active(a):
    f, kind = active_file(getattr(a, "matrix", None))
    if not f.is_file():
        sys.exit(f"matrix not found: {f}")
    return parse(f.read_text()), f, kind


def cmd_path(a):
    f, kind = active_file(a.matrix)
    print(f"{f} ({kind})")
    return 0


def cmd_show(a):
    st, f, kind = load_active(a)
    print(f"# {f} ({kind}); prices per 1M tokens in / cached / out")
    for h, p in sorted(st["plans"].items()):
        print(f"plan {h}: {p}")
    for r in st["rows"]:
        if a.host and r["host"] != a.host:
            continue
        unpriced = r["source"] in ("", "none")
        if a.unpriced and not unpriced:
            continue
        print(f"{r['host']}/{r['model']} | {','.join(r['efforts']) or '-'} | {r['price']} | {r['good']}")
    if not a.host and not a.unpriced:
        for p in st["picks"]:
            print(f"pick {p['job']}: {p['first']}" + (f"; {p['alts']}" if p["alts"] else ""))
    return 0


def cmd_pick(a):
    st, f, kind = load_active(a)
    hosts = {r["host"] for r in st["rows"]} | set(HOSTS)
    pick = next((p for p in st["picks"] if p["job"] == a.job), None)
    if pick is None:
        print(f"unknown job {a.job!r}; jobs: {', '.join(p['job'] for p in st['picks'])}", file=sys.stderr)
        return 64
    builder = author = None
    if a.job == CODE_REVIEW:
        if not a.builder:
            print("code-review needs --builder <host/model>: the reviewer must be a different model", file=sys.stderr)
            return 64
        rows_b = resolve(a.builder, st["rows"], hosts)
        if not rows_b:
            print(f"--builder {a.builder!r} is not in the matrix; name it as host/model from "
                  "`orch-models.py show`", file=sys.stderr)
            return 64
        builder = ({canon(r["model"]) for r in rows_b}, rows_b[0]["model"])
    if a.job == PLAN_REVIEW:
        if not a.author:
            print("plan-review needs --author <host>: the reviewer must be a different CLI", file=sys.stderr)
            return 64
        author = split_ref(a.author, hosts)[0] or (a.author if a.author in hosts else None)
        if author is None:
            print(f"--author must name the author's CLI ({', '.join(sorted(hosts))}), got {a.author!r}", file=sys.stderr)
            return 64

    def refusal(host, model):
        if builder and canon(model) in builder[0]:
            return f"reviewer model {model} is the builder's own model ({builder[1]})"
        if author and host == author:
            return f"reviewer CLI {host} is the plan author's CLI"
        return None

    if a.reviewer:
        found = resolve(a.reviewer, st["rows"], hosts) if a.job in (CODE_REVIEW, PLAN_REVIEW) else []
        if a.job in (CODE_REVIEW, PLAN_REVIEW) and not found:
            print(f"{'REFUSED: ' if author else ''}--reviewer {a.reviewer!r} is not in the matrix; "
                  "name it as host/model from `orch-models.py show`", file=sys.stderr)
            return 1 if author else 64
        for r in found:
            why = refusal(r["host"], r["model"])
            if why:
                print(f"REFUSED: {why}", file=sys.stderr)
                return 1
        print(f"OK: {a.reviewer} may review")
        return 0
    for c in cands(pick, hosts):
        why = cand_problem(c, st["rows"]) or refusal(c["host"], c["model"])
        if why:
            print(f"skip {c['text']}: {why}", file=sys.stderr)
            continue
        print(f"{c['host']} {c['model']} {c['effort']}")
        return 0
    print(f"no allowed candidate for {a.job} in {f}; run the models command or pick by hand", file=sys.stderr)
    return 1


def cmd_discover(a):
    print(json.dumps(discover_all(a.claude_models), indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="orch-models.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("path", "show", "pick"):
        p = sub.add_parser(name)
        p.add_argument("--matrix")
    sub.choices["show"].add_argument("--host")
    sub.choices["show"].add_argument("--unpriced", action="store_true")
    pk = sub.choices["pick"]
    pk.add_argument("job")
    pk.add_argument("--builder")
    pk.add_argument("--author")
    pk.add_argument("--reviewer")
    d = sub.add_parser("discover")
    d.add_argument("--claude-models")
    r = sub.add_parser("rebuild")
    r.add_argument("--claude-models")
    r.add_argument("--prices")
    r.add_argument("--plan", action="append")
    r.add_argument("--out", help="write here instead of the user's matrix")
    a = ap.parse_args()
    sys.exit({"path": cmd_path, "show": cmd_show, "pick": cmd_pick,
              "discover": cmd_discover, "rebuild": cmd_rebuild}[a.cmd](a))


if __name__ == "__main__":
    main()
