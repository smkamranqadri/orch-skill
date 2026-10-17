#!/usr/bin/env python3
"""measure-live: run the phase 0 live start cases headless on each host and record usage.

Usage:
  measure-live.py run --home <test-home> --out <dir> [--host <name>]... [--case <name>]...
  measure-live.py summary <out-dir>

Each run builds its fixture fresh, so every host starts from identical files. Hosts run headless
with permissions bypassed, inside the fixture, with HOME and the XDG dirs in the test home and
every HERDR_* variable removed. The run refuses to start while herdr can still reach a server,
and stops if a host replaces a linked credential file.

Cases (plan 2026-10-17, phase 0; headless deviations approved by the owner 2026-10-17):
  fix            KIS repo: start step, then the Next action (a small bug fix with a test)
  resume-clear   after `fix` with no sync, a fresh process (stands in for /clear) lists what is left
  resume-reopen  fix, then the KIS sync step; a fresh process lists what is left
  no-kis         repo without kis/: orch start step, then the fix named in TODO.md

Recorded per session: the host's own usage fields (raw) and in/out totals, the final message,
lines ending in "?" in it (questions to the owner; a heuristic), and whether the tests pass after.
The resume cases score the INVENTORY block against the seeded tasks and decisions: missing ids
are forgotten work, a done task listed as unfinished is stale.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent
HOSTS = ["claude", "codex", "cmd", "agy"]
CASES = ["fix", "resume-clear", "resume-reopen", "no-kis"]
TIMEOUT = 900

# Approved 2026-10-17: mid tier per host; cmd and agy on their default model and effort (cmd's
# default model accepts only off, high or max as effort).
MODELS = {"claude": "claude-sonnet-5-5 (medium)", "codex": "gpt-6.1-sol (medium)",
          "cmd": "default", "agy": "default"}

EXPECTED_OPEN = {"T2", "T3", "D1", "D2"}
DONE_BY_FIX = {"T1"}

P_FIX = ("Run the KIS start step: follow .agents/skills/kis/commands/start.md. The owner confirms "
         "the proposed mode and next action in advance, so do not wait for confirmation: then do "
         "the Next action and run the tests with `python3 -m unittest`. Do not commit.")
P_SYNC = (" When the tests pass, run the KIS sync step: follow .agents/skills/kis/commands/sync.md. "
          "Do not commit.")
P_INV = ("Run the KIS start step: follow .agents/skills/kis/commands/start.md. Do not change any "
         "file. After the report, add a block: a line `INVENTORY`, then every unfinished task and "
         "every open decision in this project, one per line as `<id>: <one-line summary>`, then a "
         "line `END`.")
P_ORCH = ("Run the orch start step: follow ~/.agents/skills/orch/commands/start.md. The owner "
          "approves in advance, so do not wait: then fix the bug described in TODO.md and run the "
          "tests with `python3 -m unittest`. Do not commit.")

WORDS_BUGGY = '''def word_count(text):
    """Number of words in text."""
    return len(text.split(" "))
'''

WORDS_TEST = '''import unittest

from words import word_count


class WordCountTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(word_count("one two three"), 3)

    def test_empty(self):
        self.assertEqual(word_count(""), 0)

    def test_extra_spaces(self):
        self.assertEqual(word_count("one  two "), 2)


if __name__ == "__main__":
    unittest.main()
'''

KIS_STATE = '''# Current

- Branch: `main`.
- Task: T1, fix `word_count` (plan `kis/intent/plan.md`). Mode: Fast. Status: not started.
- Blocker: none.
- Next: T1. `word_count("")` returns 1 and double spaces count as words; `test_empty` and
  `test_extra_spaces` fail.
- Proof on record: none.
- Command: `python3 -m unittest`.
'''

KIS_PLAN = '''# Plan: pebble-notes 0.2

Status: approved by the owner.

## Tasks

- T1: fix `word_count` for empty text and repeated spaces (`words.py`). Accept: `python3 -m
  unittest` green.
- T2: add a `--json` flag to the `pebble` command that prints the counts as JSON.
- T3: add a Usage section to README.md with one example per flag.

## Open decisions (owner)

- D1: licence, MIT or Apache-2.0. Waiting on the owner.
- D2: whether `word_count` treats Windows line endings as separators. Waiting on the owner.
'''

KIS_KNOWLEDGE = '''# pebble-notes

A tiny command-line word counter, written to test agent tooling. Python 3, stdlib only.
Tests: `python3 -m unittest` from the repo root.
'''

PLAIN_AGENTS = '''# Agent Instructions

tidepool-cli: a tiny command-line word counter. Python 3, stdlib only.
Tests: `python3 -m unittest` from the repo root.
'''

PLAIN_TODO = '''# TODO

- `word_count("")` returns 1 and double spaces count as words (`words.py`); `test_empty` and
  `test_extra_spaces` fail.
'''


def sh(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, capture_output=True, text=True)


def git_init(repo):
    sh(["git", "init", "-q", "-b", "main"], repo)
    sh(["git", "add", "-A"], repo)
    sh(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-q", "-m", "fixture"], repo)


def build_kis(repo):
    repo.mkdir(parents=True)
    (repo / "words.py").write_text(WORDS_BUGGY)
    (repo / "test_words.py").write_text(WORDS_TEST)
    (repo / "README.md").write_text("# pebble-notes\n\nA tiny word counter.\n")
    (repo / "AGENTS.md").write_text("# Agent Instructions\n\npebble-notes: a tiny word counter.\n")
    for layer, name, text in [("state", "current.md", KIS_STATE), ("intent", "plan.md", KIS_PLAN),
                              ("knowledge", "project.md", KIS_KNOWLEDGE)]:
        (repo / "kis" / layer).mkdir(parents=True)
        (repo / "kis" / layer / name).write_text(text)
    shutil.copytree(SOURCE / ".agents" / "skills" / "kis", repo / ".agents" / "skills" / "kis",
                    ignore=shutil.ignore_patterns("__pycache__"))
    kis = repo / ".agents" / "skills" / "kis" / "scripts"
    sh([str(kis / "install-anchor.sh"), "--target", str(repo), "--instructions",
        str(repo / "AGENTS.md")], repo)
    sh([str(kis / "install-commands.sh"), "--target", str(repo)], repo)
    git_init(repo)


def build_plain(repo):
    repo.mkdir(parents=True)
    (repo / "words.py").write_text(WORDS_BUGGY)
    (repo / "test_words.py").write_text(WORDS_TEST)
    (repo / "AGENTS.md").write_text(PLAIN_AGENTS)
    (repo / "TODO.md").write_text(PLAIN_TODO)
    git_init(repo)


def host_env(home):
    """The owner's environment with HOME and the XDG dirs moved into the test home and every
    HERDR_* variable removed, so no agent can find the owner's Herdr server (its socket lives
    under XDG_CONFIG_HOME). XDG_RUNTIME_DIR stays: agy's login is in the system keyring."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
    env["HOME"] = str(home)
    for var, sub in [("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_DATA_HOME", ".local/share"), ("XDG_CACHE_HOME", ".cache")]:
        env[var] = str(home / sub)
        (home / sub).mkdir(parents=True, exist_ok=True)
    return env


CREDENTIALS = [".claude/.credentials.json", ".codex/auth.json", ".commandcode/auth.json"]


def check_links(home):
    """Stop when a host replaced a linked credential file with its own copy: the owner's real
    login could then go stale."""
    bad = [c for c in CREDENTIALS if (home / c).exists() and not (home / c).is_symlink()]
    if bad:
        sys.exit("Error: credential link replaced by a file: " + ", ".join(bad))


def herdr_isolated(home):
    """True when herdr, run as the agents run it, reaches no server."""
    if not shutil.which("herdr"):
        return True
    r = subprocess.run(["herdr", "agent", "list"], env=host_env(home), capture_output=True,
                       text=True, stdin=subprocess.DEVNULL, timeout=20)
    return r.returncode != 0


def host_cmd(host, prompt):
    if host == "claude":
        return ["claude", "-p", prompt, "--model", "claude-sonnet-5-5", "--effort", "medium",
                "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
    if host == "codex":
        return ["codex", "exec", "--json", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium",
                "-s", "workspace-write", prompt]
    if host == "cmd":
        return ["cmd", "-p", prompt, "--output-format", "json", "--yolo", "--trust"]
    if host == "agy":
        return ["agy", "-p", prompt, "--output-format", "stream-json",
                "--dangerously-skip-permissions"]
    raise ValueError(host)


def events(path):
    out = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def parse(host, path):
    """Return (raw usage, tokens in, tokens out, final text) from a host's JSON stream."""
    evs = events(path)
    raw, tin, tout, text = None, None, None, ""
    if host == "claude":
        for e in evs:
            if e.get("type") == "result":
                raw, text = e.get("usage"), e.get("result") or ""
        if raw:
            tin = sum(raw.get(k) or 0 for k in
                      ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            tout = raw.get("output_tokens")
    elif host == "codex":
        turns = [e["usage"] for e in evs if e.get("type") == "turn.completed" and e.get("usage")]
        if turns:
            raw = {k: sum(t.get(k) or 0 for t in turns) for k in turns[-1]}
            tin = raw.get("input_tokens")  # includes cached input
            tout = (raw.get("output_tokens") or 0)
        msgs = [e["item"].get("text", "") for e in evs if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "agent_message"]
        text = msgs[-1] if msgs else ""
    elif host == "cmd":
        for e in evs:
            if e.get("type") == "result":
                raw, text = e.get("usage"), e.get("finalText") or ""
        if raw:
            tin = sum(raw.get(k) or 0 for k in ("inputTokens", "cacheReadTokens", "cacheWriteTokens"))
            tout = raw.get("outputTokens")
    elif host == "agy":
        for e in evs:
            if e.get("event") == "result":
                r = e.get("result") or {}
                raw, text = r.get("usage"), r.get("response") or ""
        if raw:
            tin = (raw.get("input_tokens") or 0) + (raw.get("cache_read_tokens") or 0)
            tout = raw.get("output_tokens")  # includes thinking_tokens (total = input + output)
    return raw, tin, tout, text


def inventory(text):
    """Ids listed between INVENTORY and END lines, or None when there is no block."""
    m = re.search(r"^\W*INVENTORY\W*$(.*?)^\W*END\W*$", text, re.M | re.S)
    if not m:
        return None
    return sorted(set(re.findall(r"\b([TD]\d+)\b", m.group(1))))


def tests_pass(repo):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=repo, env=env,
                       capture_output=True, text=True)
    return r.returncode == 0


def session(host, prompt, repo, home, rundir, name):
    log = rundir / f"{name}.ndjson"
    err = rundir / f"{name}.stderr"
    start = time.time()
    with log.open("w") as out, err.open("w") as errf:
        try:
            p = subprocess.run(host_cmd(host, prompt), cwd=repo, env=host_env(home), stdout=out,
                               stderr=errf, stdin=subprocess.DEVNULL, timeout=TIMEOUT)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    check_links(home)
    raw, tin, tout, text = parse(host, log)
    (rundir / f"{name}.final.txt").write_text(text)
    questions = sum(1 for ln in text.splitlines() if ln.rstrip().endswith("?"))
    return {"session": name, "rc": rc, "seconds": round(time.time() - start, 1), "usage": raw,
            "tokens_in": tin, "tokens_out": tout, "questions": questions}


def run_case(host, case, home, out):
    rundir = out / host / case
    if rundir.exists():
        shutil.rmtree(rundir)
    rundir.mkdir(parents=True)
    repo = rundir / "repo"
    rec = {"host": host, "case": case, "model": MODELS[host], "sessions": []}
    if case == "no-kis":
        build_plain(repo)
        rec["sessions"].append(session(host, P_ORCH, repo, home, rundir, "a"))
        rec["tests_pass"] = tests_pass(repo)
    else:
        build_kis(repo)
        first = P_FIX + (P_SYNC if case == "resume-reopen" else "")
        rec["sessions"].append(session(host, first, repo, home, rundir, "a"))
        rec["tests_pass"] = tests_pass(repo)
        if case != "fix":
            rec["sessions"].append(session(host, P_INV, repo, home, rundir, "b"))
            ids = inventory((rundir / "b.final.txt").read_text())
            rec["inventory"] = ids
            if ids is not None:
                rec["missing"] = sorted(EXPECTED_OPEN - set(ids))
                rec["stale"] = sorted(DONE_BY_FIX & set(ids)) if rec["tests_pass"] else []
    status = sh(["git", "status", "--short"], repo, check=False).stdout
    (rundir / "git-status.txt").write_text(status)
    (rundir / "record.json").write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def versions(home):
    env = host_env(home)
    out = {}
    for host, cmd in [("claude", ["claude", "--version"]), ("codex", ["codex", "--version"]),
                      ("cmd", ["cmd", "--version"]), ("agy", ["agy", "--version"])]:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        out[host] = (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "?"
    return out


def summary(out):
    meta = json.loads((out / "meta.json").read_text())
    print(f"# measure-live {meta['date']} (headless; tokens from each host's own usage fields)")
    print("# versions: " + ", ".join(f"{h} {v}" for h, v in meta["versions"].items()))
    print("host\tcase\tmodel\tsession\trc\ttokens_in\ttokens_out\tquestions\ttests_pass\tinventory\tmissing\tstale")
    for host in HOSTS:
        for case in CASES:
            f = out / host / case / "record.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text())
            for s in r["sessions"]:
                inv = ",".join(r.get("inventory") or []) if s["session"] == "b" else ""
                if s["session"] == "b" and r.get("inventory") is None:
                    inv = "no block"
                print("\t".join(str(x) for x in [
                    host, case, r["model"], s["session"], s["rc"], s["tokens_in"], s["tokens_out"],
                    s["questions"], r["tests_pass"] if s["session"] == "a" else "",
                    inv, ",".join(r.get("missing", [])) if s["session"] == "b" else "",
                    ",".join(r.get("stale", [])) if s["session"] == "b" else ""]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--home", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    r.add_argument("--host", action="append", choices=HOSTS)
    r.add_argument("--case", action="append", choices=CASES)
    s = sub.add_parser("summary")
    s.add_argument("out", type=Path)
    a = ap.parse_args()
    if a.cmd == "summary":
        summary(a.out)
        return
    home = a.home.resolve()
    if not (home / ".agents" / "skills" / "orch" / "SKILL.md").exists():
        sys.exit(f"Error: no orch install in test home {home}")
    check_links(home)
    if not herdr_isolated(home):
        sys.exit("Error: herdr reaches a server from the test environment; refusing to run")
    a.out.mkdir(parents=True, exist_ok=True)
    meta_f = a.out / "meta.json"
    meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
    meta.update({"date": time.strftime("%Y-%m-%d"), "versions": versions(home), "home": str(home)})
    meta_f.write_text(json.dumps(meta, indent=1) + "\n")
    for host in a.host or HOSTS:
        for case in a.case or CASES:
            rec = run_case(host, case, home, a.out)
            print(f"{host} {case}: " + "; ".join(
                f"{s['session']} rc={s['rc']} in={s['tokens_in']} out={s['tokens_out']}"
                for s in rec["sessions"]) + f"; tests_pass={rec['tests_pass']}", flush=True)
    summary(a.out)


if __name__ == "__main__":
    main()
