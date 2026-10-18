#!/usr/bin/env python3
"""orch-gate: split gate (run now / queue / sequential) and diff-review gate before merge.

  orch-gate.py admit <dir> <task> --owns <paths> [--depends <tasks>]
        compare <task> with every active task in <dir>/ledger.md. Prints the verdict line, then
        `status: <cell text>` for its ledger row. Exit 0 run now; 3 held (queue or sequential);
        2 usage or an unreadable ledger or an unknown dependency.
  orch-gate.py release <dir> [--apply]
        for each `queued: after <task>` row, in ledger order: `release <name>` when nothing active
        blocks it now, else `hold <name> after <blocker>`. --apply rewrites a held row's blocker
        when it changed. A released row keeps its text until task.md launches it.
  orch-gate.py review <dir> <agent> --repo <path> --range <base>..<head> --author <cli/model>
        --reviewer <cli/model> --verdict pass|fail
        record a diff review in <dir>/reviews.log (full shas). Both names resolve in the model
        matrix (orch-models.py: any spelling of the model, or a Claude alias); the reviewer must
        be a different model than the author, else exit 2.
  orch-gate.py archive <dir>
        a ledger marked `Run closed <date>`: move every file in <dir> (not folders) into
        <dir>/run-<date>[-n]/, so the next run starts empty. Exit 2 when the run is not closed.
  orch-gate.py merge-check <dir> <agent> --repo <path> --branch <name> [--target main]
        exit 0 when the latest review passed and covers the branch from its fork point to its
        tip; 4 no review, 5 review failed, 6 review older than the branch head, 7 range does
        not start at the fork point.
"""
import argparse
import datetime
import importlib.util
import os
import re
import subprocess
import sys

ENDED = ("merged", "closed", "gone")
NO_PATHS = ("none", "-")
SECTIONS = ("pane agents", "sub-agents and background jobs")
QUEUED = re.compile(r"^queued:\s*after\s+(\S+)", re.I)
GLOB = re.compile(r"[*?\[]")


class GateError(Exception):
    pass


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_tasks(d):
    """Task rows from both ledger tables, in order: name, status text, depends, owns."""
    path = os.path.join(d, "ledger.md")
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError as exc:
        raise GateError(f"cannot read {path}: {exc.strerror}")
    if any(line.strip() == "Ledger: minimal" for line in lines):
        raise GateError("minimal ledger: the gate needs an agents ledger")
    tasks, section, header = [], None, None
    for line in lines:
        if line.startswith("## "):
            section, header = line[3:].strip().lower(), None
            continue
        if section not in SECTIONS or not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            if "name" not in header or "status" not in header:
                raise GateError(f"{section} table has no name/status header")
            continue
        if len(cells) != len(header):
            raise GateError(f"row {cells[0]!r} has {len(cells)} cells, header has {len(header)}")
        row = dict(zip(header, cells))
        name = row["name"].split()[0] if row["name"].split() else ""
        if not name or name.startswith("<"):
            continue
        word = re.match(r"[a-z]+", row["status"].lower())
        tasks.append({"name": name, "word": word.group(0) if word else "", "status": row["status"],
                      "depends": names(row.get("depends", "")), "owns": paths(row.get("owns", "")),
                      "writes_nothing": row.get("owns", "").strip().lower() in NO_PATHS})
    return tasks


def names(text):
    return [t for t in re.split(r"[,\s]+", text) if t and t.lower() != "none" and t != "-"]


def paths(text):
    return [t.removeprefix("./").rstrip("/") for t in names(text)]


def static_dir(p):
    """Directory part of a path pattern before its first wildcard ('' for a bare wildcard)."""
    m = GLOB.search(p)
    if not m:
        return p
    head = p[:m.start()]
    return head.rsplit("/", 1)[0] if "/" in head else ""


def under(child, parent):
    return parent == "" or child == parent or child.startswith(parent + "/")


def overlap(a, b):
    """True when two owned-path patterns can touch the same file (conservative for globs)."""
    if GLOB.search(a) or GLOB.search(b):
        da, db = static_dir(a), static_dir(b)
        return under(da, db) or under(db, da)
    return under(a, b) or under(b, a)


def first_overlap(owns_a, owns_b):
    for a in owns_a:
        for b in owns_b:
            if overlap(a, b):
                return a, b
    return None


def active(tasks, skip=None):
    return [t for t in tasks if t["word"] not in ENDED and t["name"] != skip]


def merged(t):
    """A dependency counts as landed when its row says merged, or closed after a merge ("closed, merged <sha>")."""
    return t["word"] == "merged" or (t["word"] == "closed" and re.search(r"\bmerged\b", t["status"].lower()) is not None)


def decide(live, others, depends, owns, tasks=(), writes_nothing=False):
    """(verdict, blocker, reason): `live` are all active rows (dependencies), `others` those it competes with.
    A task whose `owns` is none writes nothing and never conflicts; a missing or empty cell holds everything."""
    by_name = {t["name"]: t for t in live}
    ended = {t["name"]: t for t in tasks if t["word"] in ENDED and not merged(t)}
    for dep in depends:
        if dep in ended:
            return "hold", dep, f"dependency {dep} ended unmerged"
    for dep in depends:
        if dep in by_name:
            return "queue", dep, f"depends on {dep}, which has not merged"
    if writes_nothing:
        return "run", None, "it writes nothing"
    for o in others:
        if o["writes_nothing"]:
            continue
        if not o["owns"]:
            return "sequential", o["name"], f"{o['name']} records no owned paths"
        hit = first_overlap(owns, o["owns"])
        if hit:
            return "sequential", o["name"], f"owns {hit[0]} overlaps {o['name']}'s {hit[1]}"
    return "run", None, "no active task depends on or overlaps it"


def check_deps(tasks, depends, skip):
    known = {t["name"] for t in tasks}
    for dep in depends:
        if dep not in known or dep == skip:
            raise GateError(f"unknown dependency {dep!r}: no ledger row")


def cmd_admit(a):
    tasks = read_tasks(a.dir)
    owns, depends = paths(a.owns), names(a.depends or "")
    nothing = a.owns.strip().lower() in NO_PATHS
    if not owns and not nothing:
        raise GateError("--owns is required: the paths or globs the task will write, or none for a task that writes nothing")
    check_deps(tasks, depends, a.task)
    verdict, blocker, reason = decide(active(tasks, a.task), active(tasks, a.task), depends, owns, tasks, nothing)
    if verdict == "run":
        print(f"run: {reason}\nstatus: working")
        return 0
    ask = "; ask the user" if verdict == "hold" else ""
    print(f"{verdict}: {reason}{ask}\nstatus: queued: after {blocker}")
    return 3


def cmd_release(a):
    tasks = read_tasks(a.dir)
    # a queued row competes only with non-queued active rows and with queued rows above it
    kept, out = [], []
    for t in tasks:
        m = QUEUED.match(t["status"])
        if t["word"] == "queued" and m:
            live = active(tasks, t["name"])
            others = [o for o in live if o["word"] != "queued" or o in kept]
            verdict, blocker, _ = decide(live, others, t["depends"], t["owns"], tasks, t["writes_nothing"])
            kept.append(t)  # a released row will run, so later queued rows wait behind it too
            if verdict == "run":
                out.append(f"release {t['name']}")
            elif verdict == "hold":
                out.append(f"hold {t['name']}: dependency {blocker} ended unmerged; ask the user")
            else:
                out.append(f"hold {t['name']} after {blocker}")
                if a.apply and blocker != m.group(1):
                    retarget(a.dir, t["name"], blocker)
    print("\n".join(out) if out else "none queued")
    return 0


def retarget(d, name, blocker):
    path = os.path.join(d, "ledger.md")
    with open(path) as f:
        lines = f.read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        cells = line.strip().strip("|").split("|")
        if line.lstrip().startswith("|") and cells[0].split() == [name]:
            lines[i] = re.sub(r"queued:\s*after\s+\S+", f"queued: after {blocker}", line, count=1)
    with open(path, "w") as f:
        f.writelines(lines)


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if p.returncode:
        raise GateError(f"git {' '.join(args)}: {p.stderr.strip() or 'failed'}")
    return p.stdout.strip()


def matrix_models():
    """orch-models.py (the same name rules the reviewer picker uses) and the active matrix rows."""
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("orch_gate_models", os.path.join(os.path.dirname(os.path.abspath(__file__)), "orch-models.py"))
    om = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(om)
    f, _ = om.active_file(None)
    try:
        rows = om.parse(f.read_text())["rows"]
    except OSError as exc:
        raise GateError(f"cannot read the model matrix {f}: {exc.strerror}")
    return om, rows, set(om.HOSTS) | {r["host"] for r in rows}


def cmd_review(a):
    base, sep, head = a.range.partition("..")
    if not sep or not base or not head:
        raise GateError("--range must be <base>..<head>")
    if a.verdict not in ("pass", "fail"):
        raise GateError("--verdict must be pass or fail")
    om, rows, hosts = matrix_models()
    found = {}
    for role, ref in (("author", a.author), ("reviewer", a.reviewer)):
        found[role] = om.resolve(ref, rows, hosts)
        if not found[role]:
            raise GateError(f"--{role} {ref!r} is not in the model matrix; name it as host/model from `orch-models.py show`")
    shared = {om.canon(r["model"]) for r in found["author"]} & {om.canon(r["model"]) for r in found["reviewer"]}
    if shared:
        raise GateError(f"the reviewer {a.reviewer!r} is the author's own model ({a.author!r}); "
                        "a code review is a different model")
    author, reviewer = (f"{found[k][0]['host']}/{found[k][0]['model']}" for k in ("author", "reviewer"))
    b, h = git(a.repo, "rev-parse", "--verify", base + "^{commit}"), git(a.repo, "rev-parse", "--verify", head + "^{commit}")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(a.dir, "reviews.log"), "a") as f:
        f.write(f"{stamp} agent={a.agent} range={b}..{h} author={author} reviewer={reviewer} verdict={a.verdict}\n")
    print(f"recorded: {a.agent} {b[:9]}..{h[:9]} reviewer {reviewer} {a.verdict}")
    return 0


def latest_review(d, agent):
    try:
        with open(os.path.join(d, "reviews.log")) as f:
            lines = [l for l in f.read().splitlines() if f" agent={agent} " in l]
    except OSError:
        return None
    return dict(kv.split("=", 1) for kv in lines[-1].split()[1:]) if lines else None


def cmd_merge_check(a):
    r = latest_review(a.dir, a.agent)
    if r is None:
        print(f"refuse: no diff review recorded for {a.agent}")
        return 4
    if r["verdict"] != "pass":
        print(f"refuse: the latest review of {a.agent} by {r['reviewer']} failed")
        return 5
    base, head = r["range"].split("..")
    tip = git(a.repo, "rev-parse", "--verify", a.branch + "^{commit}")
    if head != tip:
        print(f"refuse: review covers {head[:9]}, branch {a.branch} is at {tip[:9]}: commits after the review")
        return 6
    fork = git(a.repo, "merge-base", a.target, tip)
    if base != fork:
        print(f"refuse: review starts at {base[:9]}, the branch forks from {a.target} at {fork[:9]}")
        return 7
    print(f"ok: {a.agent} {base[:9]}..{head[:9]} reviewed by {r['reviewer']}")
    return 0


def cmd_archive(a):
    path = os.path.join(a.dir, "ledger.md")
    try:
        with open(path) as f:
            closed = [m.group(1) for m in (re.match(r"^Run closed (\S+)\s*$", l) for l in f.read().splitlines()) if m]
    except OSError as exc:
        raise GateError(f"cannot read {path}: {exc.strerror}")
    if not closed:
        raise GateError("the ledger is not marked `Run closed <date>`: nothing to archive")
    dest, n = os.path.join(a.dir, f"run-{closed[0]}"), 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(a.dir, f"run-{closed[0]}-{n}")
    os.mkdir(dest)
    moved = sorted(e for e in os.listdir(a.dir) if os.path.isfile(os.path.join(a.dir, e)))
    for e in moved:
        os.rename(os.path.join(a.dir, e), os.path.join(dest, e))
    print(f"archived {len(moved)} files to {dest}")
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="orch-gate.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("admit")
    s.add_argument("dir"), s.add_argument("task"), s.add_argument("--owns", default=""), s.add_argument("--depends")
    s.set_defaults(fn=cmd_admit)
    s = sub.add_parser("release")
    s.add_argument("dir"), s.add_argument("--apply", action="store_true")
    s.set_defaults(fn=cmd_release)
    s = sub.add_parser("review")
    s.add_argument("dir"), s.add_argument("agent")
    for opt in ("--repo", "--range", "--author", "--reviewer", "--verdict"):
        s.add_argument(opt, required=True)
    s.set_defaults(fn=cmd_review)
    s = sub.add_parser("merge-check")
    s.add_argument("dir"), s.add_argument("agent"), s.add_argument("--repo", required=True)
    s.add_argument("--branch", required=True), s.add_argument("--target", default="main")
    s.set_defaults(fn=cmd_merge_check)
    s = sub.add_parser("archive")
    s.add_argument("dir")
    s.set_defaults(fn=cmd_archive)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except GateError as exc:
        print(f"orch-gate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
