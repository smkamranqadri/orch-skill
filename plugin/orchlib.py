#!/usr/bin/env python3
"""Core orch registry and Herdr helpers (Python 3.11+)."""
from __future__ import annotations
import fcntl, hashlib, json, os, re, shlex, shutil, signal, stat, subprocess, sys, tempfile, time, tomllib, uuid
from pathlib import Path
from contextlib import contextmanager

def fail(message):
    print(f"orch: {message}", file=sys.stderr); raise SystemExit(1)
def require_runtime():
    if sys.version_info < (3,11): fail("Python 3.11 or newer is required")
    if not os.environ.get("HERDR_ENV"): fail("must run inside Herdr (HERDR_ENV is unset)")
    if not os.environ.get("HERDR_SESSION") or not os.environ.get("HERDR_PANE_ID"): fail("HERDR_SESSION and HERDR_PANE_ID are required")
def registry_path(): return Path(os.environ.get("XDG_STATE_HOME", Path.home()/".local/state"))/"orch"/"registry.json"
@contextmanager
def locked():
    path=registry_path(); path.parent.mkdir(parents=True,exist_ok=True)
    with open(path.with_name("registry.lock"),"a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            if path.exists():
                try: data=json.loads(path.read_text())
                except (OSError,json.JSONDecodeError) as exc: fail(f"cannot read registry: {exc}")
            else: data={"version":1,"orchs":{},"agents":{}}
            try:
                yield data
            except BaseException:
                save_registry(path,data)
                raise
            else:
                save_registry(path,data)
        finally: fcntl.flock(lock,fcntl.LOCK_UN)
def save_registry(path,data):
    fd,tmp=tempfile.mkstemp(prefix="registry.",dir=path.parent)
    try:
        with os.fdopen(fd,"w") as stream:
            json.dump(data,stream,indent=2,sort_keys=True); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def herdr(*args,check=True,missing_workspace_ok=False,return_errors=False,return_status=False):
    try:
        p=subprocess.run(["herdr",*map(str,args)],text=True,capture_output=True)
    except FileNotFoundError as exc:
        p=subprocess.CompletedProcess(["herdr",*map(str,args)],127,"",str(exc))
    if check and p.returncode:
        error=(p.stderr or p.stdout).strip()
        if missing_workspace_ok and args[:3]==("pane","list","--workspace") and "workspace not found" in error.lower(): return {"missing_workspace":True}
        fail(f"herdr {' '.join(map(str,args))} failed: {error}")
    if return_status:
        output=(p.stdout or p.stderr).strip()
        if not output:
            decoded={}
        else:
            try: decoded=json.loads(output)
            except json.JSONDecodeError: decoded={"raw":output}
        return p.returncode==0,decoded
    if p.returncode:
        if not return_errors: return None
        output=(p.stdout or p.stderr).strip()
        try: return json.loads(output)
        except json.JSONDecodeError: return {"error":{"code":"command_failed","message":output or f"exit {p.returncode}"}}
    if not p.stdout.strip(): return {}
    try: return json.loads(p.stdout)
    except json.JSONDecodeError: return {"raw":p.stdout.strip()}
def result(obj,*keys):
    for key in keys: obj=obj.get(key,{}) if isinstance(obj,dict) else {}
    return obj if isinstance(obj,dict) else {}
def session_key(name): return f"{os.environ['HERDR_SESSION']}/{name}"
def project_and_tree(cwd=None):
    cwd=cwd or os.getcwd()
    t=subprocess.run(["git","-C",cwd,"rev-parse","--show-toplevel"],text=True,capture_output=True)
    c=subprocess.run(["git","-C",cwd,"rev-parse","--path-format=absolute","--git-common-dir"],text=True,capture_output=True)
    if t.returncode or c.returncode: fail("current directory is not in a git repository")
    tree=str(Path(t.stdout.strip()).resolve()); common=Path(c.stdout.strip()).resolve()
    project=str((common.parent if common.name==".git" else common).resolve())
    return project,tree
DEFAULT_PROMPTS_PER_HOUR = 6
PROMPT_WINDOW_SECONDS = 3600
SPAWN_START_ATTEMPTS = int(os.environ.get("ORCH_START_POLL_ATTEMPTS", "15"))
SPAWN_START_INTERVAL = float(os.environ.get("ORCH_START_POLL_INTERVAL", "0.5"))

def prompts_per_hour():
    path = Path.home() / ".config/orch/config.toml"
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        value = config.get("cap", {}).get("prompts_per_hour", DEFAULT_PROMPTS_PER_HOUR)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return DEFAULT_PROMPTS_PER_HOUR
        return value
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, AttributeError):
        return DEFAULT_PROMPTS_PER_HOUR

def deliver(data, now=None, only=None):
    session=os.environ["HERDR_SESSION"] + "/"
    now = time.time() if now is None else now
    limit = prompts_per_hour()
    for key,orch in data["orchs"].items():
        if not key.startswith(session): continue
        if only is not None and key != only: continue
        orch["queue"] = unique_messages(orch.get("queue", []))
        if orch.get("gone") or not orch.get("queue"): continue
        if orch.get("paused"):
            orch["paused"]["count"] = len(orch["queue"])
            continue
        times = [stamp for stamp in orch.get("prompt_times", []) if now - stamp < PROMPT_WINDOW_SECONDS]
        orch["prompt_times"] = times
        if len(times) >= limit:
            orch["paused"] = {"count": len(orch["queue"]), "time": now}
            continue
        live=herdr("agent","get",orch["pane"],check=False) or {}
        live_agent=result(live,"result","agent")
        status=live_agent.get("agent_status") or live_agent.get("status") or result(live,"result").get("agent_status") or result(live,"result").get("status") or "unknown"
        if status not in ("idle","done"): continue
        message="\n".join(orch["queue"])
        if herdr("agent","prompt",orch["pane"],message,check=False) is not None:
            orch["queue"].clear(); orch["status"]="working"; times.append(now)
            orch["prompt_times"] = times

def resume(name=None):
    require_runtime()
    who = session_key(os.environ["HERDR_PANE_ID"])
    with locked() as data:
        require_registered(data)
        if name is None:
            target = who
        else:
            prefix = os.environ["HERDR_SESSION"] + "/"
            candidates = [(key, orch) for key, orch in data["orchs"].items()
                          if key.startswith(prefix) and not orch.get("gone")
                          and (orch.get("name") == name or orch.get("pane") == name)]
            if len(candidates) > 1:
                fail(f"ambiguous orch target: {name}")
            if not candidates:
                fail(f"unknown orch: {name}")
            target = candidates[0][0]
        if target not in data["orchs"] or data["orchs"][target].get("gone"):
            fail(f"unknown orch: {name or os.environ['HERDR_PANE_ID']}")
        selected = data["orchs"][target]
        selected.pop("paused", None)
        selected["prompt_times"] = []
        deliver(data, only=target)
def unique_messages(messages):
    return list(dict.fromkeys(messages))
def require_registered(data=None):
    key=session_key(os.environ.get("HERDR_PANE_ID", ""))
    if data is not None:
        if key not in data["orchs"] or data["orchs"][key].get("gone"): fail("caller is not a registered orch")
        return key
    with locked() as current:
        if key not in current["orchs"] or current["orchs"][key].get("gone"): fail("caller is not a registered orch")
    return key
def agent_names(value):
    found=[]
    def visit(node):
        if isinstance(node,dict):
            if isinstance(node.get("name"),str): found.append(node["name"])
            for child in node.values(): visit(child)
        elif isinstance(node,list):
            for child in node: visit(child)
    visit(value); return found
def pane_ids(value):
    found=[]
    def visit(node):
        if isinstance(node,dict):
            if isinstance(node.get("pane_id"),str): found.append(node["pane_id"])
            for child in node.values(): visit(child)
        elif isinstance(node,list):
            for child in node: visit(child)
    visit(value); return found

def active_agent(data, pane, session):
    prefix=session + "/"
    active=[(key,entry) for key,entry in data["agents"].items()
            if key.startswith(prefix) and entry.get("pane")==pane
            and entry.get("state")!="closed" and not entry.get("agent_closed")]
    return max(active,key=lambda item:item[1].get("since",0),default=(None,None))

def newer_agent_holds_resource(data, key, kind, ident, session):
    rows=list(data["agents"].items())
    old_index=next((index for index,(row_key,_) in enumerate(rows) if row_key==key),-1)
    old_since=data["agents"].get(key,{}).get("since",0)
    for index,(row_key,row) in enumerate(rows):
        if not row_key.startswith(session + "/"): continue
        if row_key==key or row.get("state")=="closed" or row.get("agent_closed"): continue
        if row.get("since",0)<old_since or (row.get("since",0)==old_since and index<old_index): continue
        if kind=="pane" and row.get("pane")==ident: return True
        if kind=="workspace" and (row.get("workspace")==ident or (row.get("pane") or "").startswith(f"{ident}:") or f"workspace:{ident}" in row.get("created",[]) or f"worktree:{ident}" in row.get("created",[])): return True
    return False

def drop_reused_resource(agent, kind, ident):
    print(f"orch: leaving reused {kind} {ident} open")
    agent["created"].remove(f"{kind}:{ident}")

def agent_info(target):
    response=herdr("agent","get",target,check=False)
    return result(response,"result","agent")

def sequence_value(info, key):
    value=info.get(key)
    return value if isinstance(value,int) and not isinstance(value,bool) else None

def wait_for_spawn(pane, baseline):
    for attempt in range(SPAWN_START_ATTEMPTS):
        info=agent_info(pane)
        changed=any(sequence_value(info,key) is not None and (baseline.get(key) is None or sequence_value(info,key)>baseline[key])
                    for key in ("state_change_seq","completion_seq"))
        if info.get("agent_status")=="working" or changed:
            return True
        if attempt + 1 < SPAWN_START_ATTEMPTS:
            time.sleep(SPAWN_START_INTERVAL)
    return False
def reconcile_orchs(data):
    prefix=os.environ["HERDR_SESSION"] + "/"
    entries=[(key,entry) for key,entry in data["orchs"].items() if key.startswith(prefix) and not entry.get("gone")]
    workspaces={}
    for key,entry in entries:
        workspace_id=entry.get("workspace")
        if not workspace_id: return False
        workspaces.setdefault(workspace_id,[]).append((key,entry))
    gone=[]
    for workspace_id,workspace_entries in workspaces.items():
        succeeded,listing=herdr("pane","list","--workspace",workspace_id,check=False,return_status=True)
        if not succeeded: return False
        result_data=result(listing,"result")
        panes=result_data.get("panes")
        if not isinstance(panes,list) or any(not isinstance(pane,dict) or not isinstance(pane.get("pane_id"),str) or not pane["pane_id"] for pane in panes): return False
        live_ids={pane["pane_id"] for pane in panes}
        gone.extend(entry for _,entry in workspace_entries if entry.get("pane") not in live_ids)
    for entry in gone:
        entry["gone"]=True
    return True
def workspace():
    v=os.environ.get("HERDR_WORKSPACE_ID")
    if not v: fail("HERDR_WORKSPACE_ID is required")
    return v

def current_pane():
    succeeded,response=herdr("pane","current","--current",check=False,return_status=True)
    pane=result(response,"result","pane").get("pane_id") if succeeded else None
    if not isinstance(pane,str) or not pane:
        fail("could not resolve current pane; re-run orch register from the orch pane")
    return pane

def pane_has_running_agent(pane):
    succeeded,response=herdr("agent","get",pane,check=False,return_status=True)
    if succeeded:
        result_data=result(response,"result")
        agent=result_data.get("agent")
        if isinstance(agent,dict) and agent:
            return True
        return None
    error=result(response,"error")
    code=str(error.get("code", "")).lower()
    message=str(error.get("message", "")).lower()
    if code in {"agent_not_found", "agent_not_running", "not_found", "not_running"} or "agent not found" in message or "agent not running" in message:
        return False
    return None

def board_command(a):
    if sys.stdin.isatty() and sys.stdout.isatty():
        succeeded,response=herdr("pane","current","--current",check=False,return_status=True)
        pane=result(response,"result","pane").get("pane_id") if succeeded else None
        if not isinstance(pane,str) or not pane: pane=None
        if pane and pane_has_running_agent(pane) is False:
            command=[sys.executable,str(Path(__file__).with_name("board.py"))]
            if a.once: command.append("--once")
            if a.width is not None: command.extend(["--width",str(a.width)])
            completed=subprocess.run(command,check=False)
            return completed.returncode
    command=["herdr","plugin","action","invoke","board-full","--plugin","orch"]
    try:
        opened=subprocess.run(command,text=True,capture_output=True,check=False)
    except FileNotFoundError as exc:
        print(f"orch board: could not launch herdr: {exc}", file=sys.stderr)
        print(" ".join(command))
        return 127
    if opened.returncode:
        diagnostic=(opened.stderr or opened.stdout).strip()
        if diagnostic:
            print(f"orch board: overlay failed: {diagnostic}", file=sys.stderr)
        print(" ".join(command))
        return opened.returncode
    return 0

def carry_delivery_state(recipient, donors, now=None):
    now = time.time() if now is None else now
    prompt_times = list(recipient.get("prompt_times", []))
    paused_records = []
    if recipient.get("paused"):
        paused_records.append(recipient["paused"])
    for donor in donors:
        prompt_times.extend(donor.get("prompt_times", []))
        if donor.get("paused"):
            paused_records.append(donor["paused"])
    recipient["prompt_times"] = [stamp for stamp in prompt_times if now - stamp < PROMPT_WINDOW_SECONDS]
    if paused_records:
        pause_times = [record.get("time") for record in paused_records
                       if isinstance(record, dict) and isinstance(record.get("time"), (int, float))]
        recipient["paused"] = {
            "count": len(unique_messages(recipient.get("queue", []))),
            "time": min(pause_times, default=now),
        }

def register(name=None):
    require_runtime(); pane=current_pane(); project,_=project_and_tree(); key=session_key(pane); name=name or "orch"
    direction=os.environ.get("ORCH_BOARD_DIRECTION","right")
    if direction not in ("right","down"): fail("ORCH_BOARD_DIRECTION must be 'right' or 'down'")
    with locked() as d:
        reconcile_orchs(d)
        already_registered=key in d["orchs"] and not d["orchs"][key].get("gone")
        session=os.environ["HERDR_SESSION"] + "/"
        orphaned=[a for agent_key,a in d["agents"].items() if agent_key.startswith(session) and a.get("project")==project and a.get("orch","").startswith(session) and d["orchs"].get(a.get("orch"),{}).get("gone")]
        if already_registered and not orphaned:
            deliver(d); return
        if key in d["orchs"] and not already_registered:
            d["orchs"][key].update({"project":project,"name":name,"kind":os.environ.get("ORCH_KIND","claude"),"pane":pane,"workspace":workspace(),"tab":os.environ.get("HERDR_TAB_ID",""),"status":"idle","gone":False})
        elif key not in d["orchs"]:
            d["orchs"][key]={"project":project,"name":name,"kind":os.environ.get("ORCH_KIND","claude"),"pane":pane,"workspace":workspace(),"tab":os.environ.get("HERDR_TAB_ID",""),"status":"idle","gone":False,"queue":[]}
        orphaned=[a for agent_key,a in d["agents"].items() if agent_key.startswith(session) and a.get("project")==project and a.get("orch","").startswith(session) and d["orchs"].get(a.get("orch"),{}).get("gone")]
        old_owners=sorted({a.get("orch") for a in orphaned})
        donors=[d["orchs"][old_key] for old_key in old_owners if old_key in d["orchs"]]
        for old_key in old_owners:
            if old_key in d["orchs"]:
                d["orchs"][key]["queue"].extend(d["orchs"][old_key].get("queue",[]))
                d["orchs"][old_key]["queue"].clear()
        for agent in orphaned:
            agent["orch"]=key
            d["orchs"][key]["queue"].append(f"[orch] {agent['name']} {agent.get('status','unknown')} · pane {agent.get('pane','?')} · read: herdr agent read {agent['name']}")
        carry_delivery_state(d["orchs"][key], donors)
        if not already_registered:
            opened=herdr("plugin","pane","open","--plugin","orch","--entrypoint","board","--placement","split","--target-pane",pane,"--direction",direction,check=False)
            if opened is None: fail("failed step: open board pane")
        deliver(d)
PROOF_ROLES = ("build", "review")
PROOF_FIELDS = ("run_log", "run_sha256", "tree_fingerprint", "mutations_log", "guards")
PROOF_READ_LIMIT = 64 * 1024
DIGEST_READ_LIMIT = 1024 * 1024
REPRO_TIMEOUT = float(os.environ.get("ORCH_REPRO_TIMEOUT", "120"))
EXCLUDE_LINE = b"/.orch/"
PROOF_MARK = "<!-- orch:proof -->"
PROOF_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
MUTATION_RECORD = re.compile(r"([^|\s](?:[^|]*[^|\s])?) \| ([^|\s](?:[^|]*[^|\s])?) \| tripped=(True|False) \| restored byte-identical=(True|False)")
FINDING_ID = re.compile(r"F[0-9]+")
REPRO_VERDICT = re.compile(r"(F[0-9]+) (REPRODUCED|NOT-REPRODUCED|MANUAL)")
REPRO_EVIDENCE = re.compile(r"(F[0-9]+) expected=.* observed=.*")
REPRO_SHAPED = re.compile(r"F[0-9]")  # any line like this must be a well-formed evidence or result line
LIVE_FP_TTL = 10.0
LIVE_FP_TIMEOUT = 2.0
LIVE_FP_CACHE = {}
DIGEST_FILE_LIMIT = 256 * 1024 * 1024

def proof_row(agent):
    return bool(agent.get("proof")) and agent.get("role") in PROOF_ROLES
def proof_dir(agent):
    return Path(agent["tree"])/".orch"/agent["name"]
def checked_proof_dir(agent):
    """The proof dir, or fail when .orch or .orch/<name> is a symlink (it would resolve outside the row tree)."""
    base=proof_dir(agent)
    for part in (Path(agent["tree"])/".orch", base):
        if os.path.islink(part): fail(f"proof dir refused; {part} is a symlink")
    return base
def read_regular(path, limit):
    """Bytes of a regular, non-symlink file of at most limit bytes; None when missing, unreadable, special or larger."""
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    except OSError: return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): return None
        with os.fdopen(fd,"rb",closefd=False) as stream: raw=stream.read(limit+1)
    except OSError: return None
    finally: os.close(fd)
    return raw if len(raw)<=limit else None
def read_proof_text(path):
    raw=read_regular(path,PROOF_READ_LIMIT)
    if raw is None: return None
    try: return raw.decode("utf-8")
    except UnicodeDecodeError: return None
def proof_fields(text, names):
    found={}
    for line in text.splitlines():
        name,sep,value=line.partition(":")
        if sep and name in names: found[name]=value.strip()
    return found
def executable_script(path):
    try: info=os.lstat(path)
    except OSError: return False
    return stat.S_ISREG(info.st_mode) and bool(info.st_mode & stat.S_IXUSR)
def proof_present(agent):
    """Bounded presence check used by the hook and the board: no hashing, git or subprocess."""
    try: base=proof_dir(agent)
    except (KeyError, TypeError): return False
    if agent.get("role")=="build":
        text=read_proof_text(base/"handoff.md")
        if text is None: return False
        found=proof_fields(text,PROOF_FIELDS)
        return all(found.get(name) for name in PROOF_FIELDS)
    text=read_proof_text(base/"review.md")
    if text is None or parse_findings(text) is None: return False
    return executable_script(base/"repro.sh")
def resolve_proof_path(agent, value):
    path=Path(value)
    return Path(os.path.realpath(path if path.is_absolute() else Path(agent["tree"])/path))
def inside_proof_dir(agent, path):
    return str(path).startswith(os.path.realpath(proof_dir(agent))+os.sep)
def file_digest(path):
    """sha256 of a regular file's bytes (streamed, bounded), or a marker when it is absent or unreadable."""
    try: fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
    except OSError: return "absent"
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): return "special"
        digest=hashlib.sha256(); total=0
        while True:
            chunk=os.read(fd,1<<20)
            if not chunk: return digest.hexdigest()
            total+=len(chunk)
            if total>DIGEST_FILE_LIMIT: return "oversized"
            digest.update(chunk)
    except OSError: return "unreadable"
    finally: os.close(fd)
def proof_digest(agent):
    """Digest of the bytes of every proof file a verdict binds to: the handoff, the run log and the mutations log it names, or review.md and repro.sh."""
    base=proof_dir(agent); parts=[]
    if agent.get("role")=="build":
        parts.append(("handoff.md",file_digest(base/"handoff.md")))
        text=read_proof_text(base/"handoff.md"); fields=proof_fields(text,PROOF_FIELDS) if text else {}
        for name in ("run_log","mutations_log"):
            path=resolve_proof_path(agent,fields[name]) if fields.get(name) else None
            parts.append((name,path.as_posix() if path else "")); parts.append((name+" bytes",file_digest(path) if path else "absent"))
    else:
        for name in ("review.md","repro.sh"): parts.append((name,file_digest(base/name)))
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()
def live_fingerprint(tree):
    """Fingerprint of the live tree for the board: cached for LIVE_FP_TTL and bounded by LIVE_FP_TIMEOUT; None when unknown."""
    now=time.monotonic(); cached=LIVE_FP_CACHE.get(str(tree))
    if cached and now-cached[0]<LIVE_FP_TTL: return cached[1]
    try: value=fingerprint(tree,timeout=LIVE_FP_TIMEOUT)
    except RuntimeError: value=None
    LIVE_FP_CACHE[str(tree)]=(now,value)
    return value
def live_fingerprint_once(tree):
    try: return fingerprint(tree)
    except RuntimeError: return None
def verdict_binding(agent):
    return {"digest":proof_digest(agent),"test_cmd":agent.get("test_cmd")}
def proof_state(agent):
    """Board cell for an agent row: missing, present, failing, passing, or blank for rows without the proof protocol."""
    if not proof_row(agent): return ""
    verdict=agent.get("verdict") if isinstance(agent.get("verdict"),dict) else {}
    outcome=verdict.get("result") if verdict.get("result") in ("passing","failing") else ""
    if agent.get("state") in ("closing","cleanup","closed") or str(agent.get("status","")).lower()=="closed": return outcome
    if not proof_present(agent): return "missing"
    binding=verdict.get("binding") if isinstance(verdict.get("binding"),dict) else {}
    bound=all(binding.get(field)==value for field,value in verdict_binding(agent).items())
    if agent.get("role")=="review": bound=bound and "against" in binding and "want" in binding
    elif outcome and bound: bound=binding.get("fingerprint") is not None and binding.get("fingerprint")==live_fingerprint(agent["tree"])
    return outcome if outcome and bound else "present"
def git_output(tree, *args, timeout=None):
    try: done=subprocess.run(["git","-C",str(tree),*args],capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired as exc: raise RuntimeError(f"git {' '.join(args)} timed out") from exc
    if done.returncode: raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout
def fingerprint(tree, timeout=None):
    """Hash of HEAD, the binary diff against HEAD and every non-ignored untracked path with type, mode and content; a timeout (seconds) bounds the whole run."""
    deadline=None if timeout is None else time.monotonic()+timeout
    def left():
        if deadline is None: return None
        if time.monotonic()>=deadline: raise RuntimeError("fingerprint timed out")
        return deadline-time.monotonic()
    head=git_output(tree,"rev-parse","HEAD",timeout=left()).strip()
    diff=git_output(tree,"diff","HEAD","--binary","--no-ext-diff","--no-textconv","--no-color",timeout=left())
    paths=sorted(path for path in git_output(tree,"ls-files","--others","--exclude-standard","-z",timeout=left()).split(b"\0") if path)
    digest=hashlib.sha256()
    digest.update(b"HEAD\0"+head+b"\0"+b"DIFF\0"+str(len(diff)).encode()+b"\0"+diff)
    root=os.fsencode(str(tree))
    for rel in paths:
        left(); full=os.path.join(root,rel)
        try:
            info=os.lstat(full)
            if stat.S_ISLNK(info.st_mode): kind=b"link"; content=hashlib.sha256(os.readlink(full)).hexdigest()
            elif stat.S_ISREG(info.st_mode):
                kind=b"file"; hashed=hashlib.sha256()
                with open(full,"rb") as stream:
                    for chunk in iter(lambda: stream.read(1<<20),b""): hashed.update(chunk)
                content=hashed.hexdigest()
            else: raise RuntimeError(f"unsupported untracked entry: {os.fsdecode(rel)}")
        except OSError as exc: raise RuntimeError(f"cannot read {os.fsdecode(rel)}: {exc}") from exc
        digest.update(b"U\0"+rel+b"\0"+kind+b"\0"+(b"x" if info.st_mode & stat.S_IXUSR else b"-")+b"\0"+content.encode()+b"\0")
    return digest.hexdigest()
def fingerprint_command():
    top=subprocess.run(["git","rev-parse","--show-toplevel"],text=True,capture_output=True)
    if top.returncode: fail("current directory is not in a git repository")
    try: print(fingerprint(top.stdout.strip()))
    except RuntimeError as exc: fail(f"fingerprint failed: {exc}")
def ensure_excluded(tree):
    """Append /.orch/ to the checkout's info/exclude once, keeping every existing byte."""
    found=subprocess.run(["git","-C",str(tree),"rev-parse","--git-path","info/exclude"],text=True,capture_output=True)
    if found.returncode or not found.stdout.strip(): fail(f"cannot locate info/exclude for {tree}: {found.stderr.strip()}")
    path=Path(found.stdout.strip()); path=path if path.is_absolute() else Path(tree)/path
    path.parent.mkdir(parents=True,exist_ok=True)
    try: current=path.read_bytes()
    except FileNotFoundError: current=b""
    if EXCLUDE_LINE in current.split(b"\n"): return
    with open(path,"ab") as stream:
        if current and not current.endswith(b"\n"): stream.write(b"\n")
        stream.write(EXCLUDE_LINE+b"\n")
def proof_rules(role):
    here=Path(__file__).resolve().parent
    for base in (here.parent/"skills"/"orch",Path.home()/".agents"/"skills"/"orch"):
        path=base/"references"/"proof.md"
        if path.is_file():
            parts=re.split(r"^<!-- role:(build|review) -->\n",path.read_text(encoding="utf-8"),flags=re.M)
            sections=dict(zip(parts[1::2],parts[2::2]))
            if role in sections: return parts[0]+sections[role]
    fail("proof rules not found: skills/orch/references/proof.md")
def prepare_proof(agent, brief, rules):
    checked_proof_dir(agent); ensure_excluded(agent["tree"]); base=proof_dir(agent); base.mkdir(parents=True,exist_ok=True); checked_proof_dir(agent)
    text=rules.replace("{test_cmd}",agent.get("test_cmd") or "(none given)").replace("{proof_dir_q}",shlex.quote(str(base))).replace("{proof_dir}",str(base))
    current=brief.read_text(encoding="utf-8"); at=current.find(PROOF_MARK)
    head=(current[:at] if at>=0 else current).rstrip("\n")
    brief.write_text(head+"\n\n"+PROOF_MARK+"\n"+text,encoding="utf-8")
def proof_archive_path(agent):
    return registry_path().parent/"proof"/os.environ["HERDR_SESSION"]/agent["name"]
def archive_proof(agent):
    """Copy the proof dir to the archive before close removes anything; fail closed on any copy error."""
    source=checked_proof_dir(agent); target=proof_archive_path(agent)
    if not source.is_dir():
        print(f"orch: no proof directory to archive at {source}"); return
    staging=target.with_name(f"{target.name}.tmp-{os.getpid()}")
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.rmtree(staging,ignore_errors=True)
        shutil.copytree(source,staging,symlinks=True)
        retired=target.with_name(f"{target.name}.old-{time.time_ns()}")
        if target.exists(): os.rename(target,retired)
        os.rename(staging,target)
        shutil.rmtree(retired,ignore_errors=True)
    except (OSError,shutil.Error) as exc:
        shutil.rmtree(staging,ignore_errors=True)
        fail(f"close refused; cannot archive proof {source} to {target}: {exc}")
    agent["proof_archive"]=str(target)
def parse_findings(text):
    value=proof_fields(text,("findings",)).get("findings")
    if value is None: return None
    if value=="none": return []
    ids=[token.strip() for token in value.split(",")]
    return ids if ids and all(FINDING_ID.fullmatch(token) for token in ids) else None
def git_env(index):
    return os.environ|{"GIT_INDEX_FILE":str(index),"GIT_AUTHOR_NAME":"orch verify","GIT_AUTHOR_EMAIL":"verify@orch.invalid","GIT_COMMITTER_NAME":"orch verify","GIT_COMMITTER_EMAIL":"verify@orch.invalid"}
def snapshot_commit(tree, scratch):
    """Commit of the worker's current tree built in a private index; the worker's index, branch and files stay untouched."""
    env=git_env(Path(scratch)/"index")
    def run(*args):
        done=subprocess.run(["git","-C",str(tree),*args],env=env,text=True,capture_output=True)
        if done.returncode: raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout.strip()
    found=subprocess.run(["git","-C",str(tree),"rev-parse","--git-path","index"],env={k:v for k,v in env.items() if k!="GIT_INDEX_FILE"},text=True,capture_output=True)
    if found.returncode: raise RuntimeError(f"git rev-parse --git-path index failed: {found.stderr.strip()}")
    index=Path(found.stdout.strip()); index=index if index.is_absolute() else Path(tree)/index
    # Seed from the worker's real index so staged (even ignored) paths are kept; the copy is private.
    if index.is_file(): shutil.copyfile(index,env["GIT_INDEX_FILE"])
    else: run("read-tree","HEAD")
    run("add","-A")
    return run("-c","commit.gpgsign=false","commit-tree",run("write-tree"),"-p","HEAD","-m","orch verify snapshot")
def kill_group(process):
    """Kill the child's whole process group, also when the child itself already exited but left descendants."""
    if process is None: return
    try: os.killpg(process.pid,signal.SIGKILL)
    except OSError: pass
    if process.poll() is None: process.wait()
def clean_run(row, base):
    """Run the stored test command on a snapshot of the dirty tree; returns (exit code, log path)."""
    tree=row["tree"]; scratch=tempfile.mkdtemp(prefix="orch-verify-"); checkout=Path(scratch)/"tree"; process=None; added=False
    number=len(list(base.glob("verify-clean-*.log")))+1; log=base/f"verify-clean-{number}.log"
    def interrupted(signum,frame): raise KeyboardInterrupt
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        commit=snapshot_commit(tree,scratch)
        git_output(tree,"worktree","add","--detach",str(checkout),commit); added=True
        with open(log,"wb") as stream:
            process=subprocess.Popen(["/bin/sh","-c",row["test_cmd"]],cwd=checkout,stdout=stream,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
            code=process.wait()
        return code,log
    finally:
        kill_group(process)
        if added: subprocess.run(["git","-C",str(tree),"worktree","remove","--force",str(checkout)],capture_output=True)
        subprocess.run(["git","-C",str(tree),"worktree","prune"],capture_output=True)
        shutil.rmtree(scratch,ignore_errors=True)
        signal.signal(signal.SIGTERM,previous)
def verify_build(row, emit):
    base=proof_dir(row); text=read_proof_text(base/"handoff.md")
    if text is None:
        emit("FAIL",f"handoff missing or unreadable: {base/'handoff.md'}"); return
    fields=proof_fields(text,PROOF_FIELDS); missing=[name for name in PROOF_FIELDS if not fields.get(name)]
    for name in missing: emit("FAIL",f"handoff missing field {name}")
    if missing: return
    emit("PASS","handoff has every field")
    log=resolve_proof_path(row,fields["run_log"]); data=read_regular(log,1<<30)
    if data is None: emit("FAIL",f"run_log missing: {log}")
    elif not inside_proof_dir(row,log): emit("FAIL",f"run_log outside the proof dir: {log}")
    else:
        if hashlib.sha256(data).hexdigest()==fields["run_sha256"]: emit("PASS","run_sha256 matches the run log")
        else: emit("FAIL","run_sha256 does not match the run log")
        if data.rstrip(b"\n").split(b"\n")[-1]==b"exit=0": emit("PASS","run log ends with exit=0")
        else: emit("FAIL","run log does not end with exit=0")
    try: current=fingerprint(row["tree"])
    except RuntimeError as exc: emit("FAIL",f"fingerprint error: {exc}")
    else:
        if current==fields["tree_fingerprint"]: emit("PASS","tree_fingerprint unchanged")
        else: emit("FAIL","tree_fingerprint changed since the final run")
    verify_mutations(row,fields,emit)
def verify_mutations(row, fields, emit):
    path=resolve_proof_path(row,fields["mutations_log"]); declared=[] if fields["guards"]=="none" else [name.strip() for name in fields["guards"].split(",")]
    if not all(declared): emit("FAIL","guards has an empty name"); return
    if not inside_proof_dir(row,path): emit("FAIL",f"mutations_log outside the proof dir: {path}"); return
    raw=read_regular(path,DIGEST_READ_LIMIT)
    if raw is None and os.path.lexists(path): emit("FAIL",f"mutations_log unreadable: {path}"); return
    try: text="" if raw is None else raw.decode("utf-8")
    except UnicodeDecodeError: emit("FAIL","mutations.log is not UTF-8"); return
    latest={}; bad=0
    for number,line in enumerate(text.split("\n"),1):
        if not line.strip(): continue
        match=MUTATION_RECORD.fullmatch(line)
        if not match: emit("FAIL",f"mutations.log line {number} is malformed"); bad+=1; continue
        latest[match[1]]=(match[3]=="True",match[4]=="True")
    for name in sorted(set(latest)-set(declared)): emit("FAIL",f"guard {name} has a record but is not declared in guards")
    for name in declared:
        if name not in latest: emit("FAIL",f"guard {name} has no mutation record")
        elif not latest[name][0]: emit("FAIL",f"guard {name} latest record has tripped=False")
        elif not latest[name][1]: emit("FAIL",f"guard {name} latest record has restored byte-identical=False")
        else: emit("PASS",f"guard {name} tripped and restored byte-identical")
    if not declared and not latest and not bad: emit("PASS","no guards declared")
def verify_review(row, against, want, emit):
    base=proof_dir(row); text=read_proof_text(base/"review.md")
    if text is None: emit("FAIL",f"review.md missing or unreadable: {base/'review.md'}"); return
    declared=parse_findings(text)
    if declared is None: emit("FAIL","review.md has no valid findings: line"); return
    if not executable_script(base/"repro.sh"): emit("FAIL",f"repro.sh missing or not an executable file: {base/'repro.sh'}"); return
    process=None
    def interrupted(signum,frame): raise KeyboardInterrupt
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        process=subprocess.Popen([str(base/"repro.sh"),str(against)],cwd=against,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,text=True,errors="replace",start_new_session=True)
        try: output,_=process.communicate(timeout=REPRO_TIMEOUT)
        except subprocess.TimeoutExpired:
            kill_group(process); emit("FAIL",f"repro.sh timed out after {REPRO_TIMEOUT:g}s"); return
    except OSError as exc: emit("FAIL",f"repro.sh could not run: {exc}"); return
    finally:
        kill_group(process); signal.signal(signal.SIGTERM,previous)
    if process.returncode: emit("FAIL",f"repro.sh exited {process.returncode}")
    verdicts={}; evidence=set()
    for line in output.splitlines():
        if not REPRO_SHAPED.match(line): continue
        if REPRO_EVIDENCE.fullmatch(line): evidence.add(line.split(" ",1)[0])
        elif REPRO_VERDICT.fullmatch(line): verdicts.setdefault(line.split(" ",1)[0],[]).append(line.split(" ",1)[1])
        else: emit("FAIL",f"malformed repro line: {line}")
    for ident in sorted(set(verdicts)|evidence,key=lambda item:int(item[1:])):
        if ident not in declared: emit("FAIL",f"{ident} is not declared in findings")
    reasons=proof_fields_by_finding(text)
    for ident in declared:
        results=verdicts.get(ident,[])
        if not results: emit("FAIL",f"{ident} has no result line")
        elif len(results)>1: emit("FAIL",f"{ident} has {len(results)} result lines")
        elif ident not in evidence: emit("FAIL",f"{ident} has no expected/observed evidence line")
        elif results[0]=="MANUAL":
            if reasons.get(ident): emit("MANUAL",f"{ident} needs a person: {reasons[ident]}")
            else: emit("FAIL",f"{ident} is MANUAL without a reason in review.md")
        elif results[0]==want: emit("PASS",f"{ident} {results[0]}")
        else: emit("FAIL",f"{ident} is {results[0]}, wanted {want}")
    if not declared and not verdicts and process.returncode==0: emit("PASS","no findings declared")
def proof_fields_by_finding(text):
    reasons={}
    for line in text.splitlines():
        match=re.fullmatch(r"(F[0-9]+) manual: (\S.*)",line)
        if match: reasons[match[1]]=match[2].strip()
    return reasons
def verify(a):
    require_runtime(); key=session_key(a.name)
    with locked() as d:
        require_registered(d)
        found=d["agents"].get(key); row=json.loads(json.dumps(found)) if found else None
    if not row: fail(f"unknown agent: {a.name}")
    failures=[]
    def emit(kind,message):
        if kind=="FAIL": failures.append(message)
        print(f"{kind} {message}",flush=True)
    def finish():
        print("RESULT: PASS" if not failures else f"RESULT: FAIL ({len(failures)})",flush=True)
        raise SystemExit(1 if failures else 0)
    if not proof_row(row):
        emit("FAIL","no proof protocol on this row"); finish()
    if row.get("state") in ("closed","cleanup","closing") or row.get("agent_closed"):
        emit("FAIL","agent is closed"); finish()
    if row["role"]=="review":
        if a.against is None:
            print("orch verify: --against is required for a review row",file=sys.stderr); raise SystemExit(2)
        against=Path(os.path.realpath(a.against))
        if not against.is_dir(): fail(f"--against is not a directory: {a.against}")
    elif a.against is not None:
        emit("FAIL","--against applies to review rows only"); finish()
    for part in (Path(row["tree"])/".orch", proof_dir(row)):
        if os.path.islink(part): emit("FAIL",f"proof dir refused; {part} is a symlink"); finish()
    try: start=verdict_binding(row)
    except OSError as exc:
        emit("FAIL",f"cannot read proof: {exc}"); finish()
    if row["role"]=="build":
        start["fingerprint"]=live_fingerprint_once(row["tree"])
        verify_build(row,emit)
        if not failures:
            try: code,log=clean_run(row,proof_dir(row))
            except (RuntimeError,OSError) as exc: emit("FAIL",f"clean run could not start: {exc}")
            else:
                if code==0: emit("PASS",f"clean run exit=0 (log {log})")
                else: emit("FAIL",f"clean run exit={code} (log {log})")
    else:
        verify_review(row,against,a.want,emit)
        start["against"]=str(against); start["want"]=a.want
    outcome="failing" if failures else "passing"
    try: end=verdict_binding(row)
    except OSError: end=None
    if end is not None and row["role"]=="build": end["fingerprint"]=live_fingerprint_once(row["tree"])
    with locked() as d:
        current=d["agents"].get(key)
        same=bool(current) and current.get("name")==row.get("name") and current.get("proof_id")==row.get("proof_id") and current.get("since")==row.get("since") and current.get("state") not in ("closed","cleanup","closing") and not current.get("agent_closed")
        if same and end is not None and end["digest"]==start["digest"] and end.get("fingerprint")==start.get("fingerprint"):
            current["verdict"]={"result":outcome,"time":time.time(),"binding":start}
        else:
            emit("FAIL","row changed during verify")
    finish()
def spawn(a):
    require_runtime(); a.brief=Path(a.brief).expanduser().resolve()
    if not a.brief.is_file(): fail(f"brief does not exist: {a.brief}")
    proof=a.role in PROOF_ROLES; rules=None
    if a.role=="build" and not (a.test_cmd or "").strip():
        print("orch spawn: --test-cmd is required with --role build",file=sys.stderr); raise SystemExit(2)
    if proof:
        if not PROOF_NAME.fullmatch(a.name):
            print(f"orch spawn: a {a.role} worker name must match [A-Za-z0-9][A-Za-z0-9._-]*: {a.name}",file=sys.stderr); raise SystemExit(2)
        rules=proof_rules(a.role)
    project,tree=project_and_tree(); a.writes |= a.where=="worktree"; key=session_key(a.name); orch=session_key(os.environ["HERDR_PANE_ID"]); created=[]
    with locked() as d:
        require_registered(d)
        if key in d["agents"] and d["agents"][key].get("state") in ("not-started","starting","live","cleanup","closing"): fail(f"agent already exists: {a.name}")
        live=herdr("agent","list",check=False) or {}
        if a.name in agent_names(live): fail(f"agent already exists in Herdr: {a.name}")
        destination=tree if a.where!="worktree" else str((Path(project)/f"../{Path(project).name}.wt/{a.name}").resolve())
        if a.writes and any(x.get("tree")==destination and x.get("writes") and x.get("state") in ("not-started","starting","live","cleanup","closing") for x in d["agents"].values()): fail(f"writer already active in tree: {destination}")
        d["agents"][key]={"name":a.name,"pane":None,"orch":orch,"project":project,"kind":a.kind,"model":a.model,"effort":a.effort,"where":a.where,"writes":bool(a.writes),"tree":destination,"branch":f"orch/{a.name}" if a.where=="worktree" else None,"worktree":None,"role":a.role,"created":created,"state":"starting","status":"starting","since":int(time.time()),"started":False,"stopped":False,"agent_closed":False,"pane_closed":False}
        if proof: d["agents"][key].update(proof=1,proof_id=uuid.uuid4().hex,test_cmd=(a.test_cmd or "").strip() or None)
        save_registry(registry_path(),d)
        try:
            if a.where=="pane":
                layout=herdr("pane","layout","--pane",os.environ["HERDR_PANE_ID"],check=False) or {}; pane_data=result(layout,"result","pane")
                direction="right" if pane_data.get("width",0)>pane_data.get("height",0) else "down"
                out=herdr("pane","split","--pane",os.environ["HERDR_PANE_ID"],"--direction",direction,"--cwd",tree,"--no-focus"); pane=result(out,"result","pane").get("pane_id")
                if not pane: fail("failed step: create pane (missing pane id)")
                created.append(f"pane:{pane}"); save_registry(registry_path(),d)
            elif a.where=="tab":
                out=herdr("tab","create","--workspace",workspace(),"--cwd",tree,"--label",a.name,"--no-focus"); pane=result(out,"result","root_pane").get("pane_id"); tab=result(out,"result","tab").get("tab_id")
                if not pane: fail("failed step: create tab (missing pane id)")
                if tab: created.append(f"tab:{tab}")
                created.append(f"pane:{pane}"); save_registry(registry_path(),d)
            else:
                out=herdr("worktree","create","--cwd",project,"--branch",f"orch/{a.name}","--base",a.base or "HEAD","--path",f"../{Path(project).name}.wt/{a.name}","--label",a.name,"--no-focus"); pane=result(out,"result","root_pane").get("pane_id"); ws=result(out,"result","workspace").get("workspace_id"); wt=result(out,"result","worktree").get("path") or f"../{Path(project).name}.wt/{a.name}"
                if not pane or not ws: fail("failed step: create worktree (missing pane or workspace id)")
                created.extend([f"workspace:{ws}",f"worktree:{ws}",f"branch:orch/{a.name}"]); d["agents"][key].update(worktree=str((Path(project)/wt).resolve()),tree=str((Path(project)/wt).resolve())); save_registry(registry_path(),d)
            occupied_key,occupied=active_agent(d,pane,os.environ["HERDR_SESSION"])
            if occupied_key:
                fail(f"pane already held by non-closed agent: {occupied.get('name',occupied_key)} ({pane})")
            d["agents"][key]["pane"]=pane
            save_registry(registry_path(),d)
            if proof: prepare_proof(d["agents"][key],a.brief,rules)
            argv=["agent","start",a.name,"--kind",a.kind,"--pane",pane,"--"]
            if a.kind=="claude":
                if a.model: argv += ["--model",a.model]
                if a.effort: argv += ["--effort",a.effort]
            else:
                if a.model: argv += ["-m",a.model]
                if a.effort: argv += ["-c",f"model_reasoning_effort={a.effort}"]
            herdr(*argv); d["agents"][key]["started"]=True; save_registry(registry_path(),d)
            baseline_info=agent_info(pane)
            baseline={field:sequence_value(baseline_info,field) for field in ("state_change_seq","completion_seq")}
            d["agents"][key]["completion_seq"]=baseline["completion_seq"]
            d["agents"][key]["turn_open"]=True
            d["agents"][key]["seen_state_seq"]=baseline["state_change_seq"]
            d["agents"][key]["seen_completion_seq"]=baseline["completion_seq"]
            d["agents"][key]["sequence_capable"] = any(field in baseline_info for field in ("state_change_seq", "completion_seq"))
            save_registry(registry_path(),d)
            herdr("agent","prompt",a.name,f"The user asked for this: {a.brief}")
            started=wait_for_spawn(pane,baseline)
            if not started:
                herdr("agent","send-keys",a.name,"Enter",check=False)
                started=wait_for_spawn(pane,baseline)
            if not started:
                d["agents"][key].update(state="not-started",status="not-started")
                deliver(d)
                print(f"orch: agent on pane {pane} did not start; run: herdr agent send-keys {a.name} Enter",file=sys.stderr)
                raise SystemExit(1)
            d["agents"][key].update(state="live",status="working"); deliver(d)
        except BaseException as exc:
            if d["agents"].get(key,{}).get("state")=="not-started": raise
            for item in [x for x in reversed(created) if not x.startswith("branch:")]+[x for x in reversed(created) if x.startswith("branch:")]:
                kind,ident=item.split(":",1)
                if kind in ("pane","workspace") and newer_agent_holds_resource(d,key,kind,ident,os.environ["HERDR_SESSION"]):
                    drop_reused_resource(d["agents"][key],kind,ident); save_registry(registry_path(),d); continue
                ok=True
                if kind=="worktree": ok=herdr("worktree","remove","--workspace",ident,check=False) is not None
                elif kind in ("pane","tab","workspace"): ok=herdr(kind,"close",ident,check=False) is not None
                elif kind=="branch":
                    p=subprocess.run(["git","branch","-d",ident],cwd=project,text=True,capture_output=True); ok=p.returncode==0
                if not ok: break
                created.remove(item); save_registry(registry_path(),d)
            if not created: d["agents"].pop(key,None)
            else: d["agents"][key].update(state="cleanup",status="cleanup")
            if isinstance(exc,SystemExit): raise
            fail(f"failed step: spawn {a.name}: {exc}")
def adopt(a):
    require_runtime(); project,tree=project_and_tree(); owner=session_key(os.environ["HERDR_PANE_ID"])
    with locked() as d:
        require_registered(d)
        info=agent_info(a.target)
        name=info.get("name"); pane=info.get("pane_id")
        kind=info.get("agent") or info.get("kind"); status=info.get("agent_status") or info.get("status")
        if not name or not pane or not kind or not status: fail(f"unknown agent or pane: {a.target}")
        adopted_name=a.name or name
        prefix=os.environ["HERDR_SESSION"]+"/"; key=session_key(adopted_name)
        conflicts=[(old_key,entry) for old_key,entry in d["agents"].items() if old_key.startswith(prefix) and (old_key==key or entry.get("name")==adopted_name or (entry.get("pane")==pane and (entry.get("state")!="closed" and not entry.get("agent_closed"))))]
        tombstones=[]; idempotent=None
        for old_key,entry in conflicts:
            same_pane=entry.get("pane")==pane
            if (old_key==key or entry.get("name")==adopted_name) and not same_pane:
                fail(f"agent name already in use in this session: {adopted_name}")
            if not same_pane:
                continue
            if entry.get("adopted") and entry.get("orch")==owner and old_key==key and entry.get("name")==adopted_name:
                idempotent=(old_key,entry)
                continue
            if entry.get("adopted") and entry.get("orch")==owner:
                fail(f"cannot change adopted agent name from {entry.get('name',old_key)} to {adopted_name}; close it before adopting with a new name")
            if not d["orchs"].get(entry.get("orch"),{}).get("gone",True):
                fail(f"agent already owned by a live orch: {entry.get('name',name)}")
            if entry.get("created") or not entry.get("adopted"):
                fail(f"agent already exists in registry: {entry.get('name',name)}")
            tombstones.append(old_key)
        if idempotent:
            for old_key in tombstones:
                d["agents"].pop(old_key,None)
            entry=idempotent[1]
            entry.pop("closed_at",None)
            baseline=sequence_value(info,"completion_seq")
            state_baseline=sequence_value(info,"state_change_seq")
            entry.update(project=project,tree=tree,kind=kind,model=info.get("model") or "",role=a.role or entry.get("role","explore"),where="adopted",state="live",status=status,created=[],started=False,stopped=False,agent_closed=False,pane_closed=False,completion_seq=baseline,turn_open=True,seen_state_seq=state_baseline,seen_completion_seq=baseline,sequence_capable=any(field in info for field in ("state_change_seq", "completion_seq")))
            deliver(d)
            return
        for old_key in tombstones:
            d["agents"].pop(old_key,None)
        baseline=sequence_value(info,"completion_seq")
        state_baseline=sequence_value(info,"state_change_seq")
        d["agents"][key]={"name":adopted_name,"pane":pane,"orch":owner,"project":project,"kind":kind,"model":info.get("model") or "","effort":None,"where":"adopted","writes":False,"tree":tree,"branch":None,"worktree":None,"role":a.role or "explore","created":[],"state":"live","status":status,"since":int(time.time()),"started":False,"stopped":False,"agent_closed":False,"pane_closed":False,"completion_seq":baseline,"turn_open":True,"seen_state_seq":state_baseline,"seen_completion_seq":baseline,"sequence_capable":any(field in info for field in ("state_change_seq", "completion_seq")),"adopted":True}
        deliver(d)
def list_agents(a):
    require_runtime(); who=session_key(os.environ["HERDR_PANE_ID"])
    with locked() as d:
        reconcile_orchs(d)
        require_registered(d)
        current = d["orchs"][who]
        if current.get("paused"):
            current["paused"]["count"] = len(unique_messages(current.get("queue", [])))
            print(f"PAUSED: {current['paused'].get('count', 0)} notice(s) held since {current['paused'].get('time')}")
        rows=[x for x in d["agents"].values() if (a.all or x.get("orch")==who) and (not a.idle or (x.get("status")=="idle" and not x.get("proof"))) and (not a.role or x.get("role")==a.role)]
        for x in sorted(rows,key=lambda x:(x.get("role",""),x.get("name",""))): print(f"{x.get('role','?')}\t{x.get('name','?')}\t{x.get('status','unknown')}\t{x.get('where','?')}")
        deliver(d)
def verify_worktree_close(agent, wt=None):
    target = subprocess.run(["git","rev-parse","HEAD"],cwd=os.getcwd(),text=True,capture_output=True)
    if target.returncode: fail(f"close refused; cannot resolve merge target: {target.stderr.strip()}")
    target = target.stdout.strip()
    refs = []
    branch = subprocess.run(["git","rev-parse","--verify","--quiet",f"refs/heads/{agent['branch']}"],cwd=os.getcwd(),text=True,capture_output=True)
    if branch.returncode == 0: refs.append(("registered branch", branch.stdout.strip()))
    if wt:
        checkout = subprocess.run(["git","-C",wt,"rev-parse","HEAD"],text=True,capture_output=True)
        if checkout.returncode: fail(f"close refused; cannot read worktree HEAD: {checkout.stderr.strip()}")
        refs.append(("worktree HEAD", checkout.stdout.strip()))
    unmerged = []
    for label, ref in refs:
        merged = subprocess.run(["git","merge-base","--is-ancestor",ref,target],cwd=os.getcwd(),capture_output=True)
        if merged.returncode:
            commits = subprocess.run(["git","log","--oneline",f"{target}..{ref}"],cwd=os.getcwd(),text=True,capture_output=True)
            unmerged.append(f"{label}: {commits.stdout.strip() or ref}")
    owned = proof_row(agent)
    status = subprocess.run(["git","-C",wt,"status","--porcelain","-z","--ignored",*(["-uall"] if owned else [])],capture_output=True) if wt else None
    dirty = ""
    if status:
        lines = [entry for entry in status.stdout.decode(errors="surrogateescape").split("\0") if entry]
        # The row's own proof dir is archived by close, so it is not dirt; every other path still is.
        prefix = f".orch/{agent['name']}/"
        dirty = "".join(line + "\n" for line in lines if not (owned and line.startswith("!! ") and line[3:].startswith(prefix)))
    if unmerged or (status and (status.returncode or dirty)):
        dirty_paths = dirty.strip() if status else ""
        fail(f"close refused; unmerged commits: {'; '.join(unmerged) or '(none)'}; dirty paths: {dirty_paths or '(none)'}")
def close_agent(a):
    require_runtime()
    with locked() as d:
        require_registered(d)
        key=session_key(a.name); agent=d["agents"].get(key)
        if not agent: fail(f"unknown agent: {a.name}")
        if agent.get("adopted"):
            if agent.get("orch")!=session_key(os.environ["HERDR_PANE_ID"]): fail("agent is not owned by this orch")
            agent.setdefault("closed_at", time.time()); agent.update(state="closed",status="closed"); deliver(d); return
        if agent.get("state")=="closed" and not agent.get("created"):
            deliver(d); return
        if proof_row(agent):
            archive_proof(agent); save_registry(registry_path(),d)
        if agent.get("state")=="closed":
            agent["state"]="cleanup"; agent["agent_closed"]=True
        wt=agent.get("worktree")
        if wt and not a.discard:
            verify_worktree_close(agent, wt if Path(wt).exists() else None)
        agent.update(state="closing",status="closing"); save_registry(registry_path(),d)
        if agent.get("started") and not agent.get("stopped") and not agent.get("agent_closed"):
            herdr("agent","send-keys",a.name,"ctrl+c"); agent["stopped"]=True; save_registry(registry_path(),d)
        if wt and Path(wt).exists() and not a.discard:
            verify_worktree_close(agent, wt)
        for item in reversed(agent.get("created",[])):
            kind,ident=item.split(":",1)
            if kind not in ("pane","tab","workspace"): continue
            if kind in ("pane","workspace") and newer_agent_holds_resource(d,key,kind,ident,os.environ["HERDR_SESSION"]):
                drop_reused_resource(agent,kind,ident); save_registry(registry_path(),d); continue
            if herdr(kind,"close",ident,check=False) is None: fail(f"failed step: close {kind} {ident}")
            agent["created"].remove(item); save_registry(registry_path(),d)
        if any(item.startswith(("pane:","tab:","workspace:")) for item in agent.get("created",[])):
            fail(f"failed step: cleanup remains for {a.name}: {', '.join(agent['created'])}")
        if wt and not a.keep_checkout:
            ws=next((x.split(":",1)[1] for x in agent.get("created",[]) if x.startswith("worktree:")),None)
            preserved_workspace=False
            if ws:
                if newer_agent_holds_resource(d,key,"workspace",ws,os.environ["HERDR_SESSION"]):
                    drop_reused_resource(agent,"worktree",ws); save_registry(registry_path(),d)
                    preserved_workspace=True
                    ws=None
            if ws:
                missing = False
                if wt and Path(wt).exists():
                    succeeded,result = herdr("worktree","remove","--workspace",ws,check=False,return_status=True)
                    error = result.get("error") if isinstance(result, dict) else None
                    missing = not succeeded and isinstance(error, dict) and error.get("code") == "workspace_not_found"
                    if not succeeded and not missing:
                        detail = error.get("message", error) if isinstance(error, dict) else result
                        fail(f"herdr worktree remove --workspace {ws} failed: {detail}")
                elif wt:
                    subprocess.run(["git","worktree","prune"],cwd=os.getcwd(),capture_output=True)
                if missing:
                    if wt and Path(wt).exists():
                        if not a.discard: verify_worktree_close(agent, wt)
                        args = ["git","worktree","remove"]
                        if a.discard: args.append("--force")
                        args.append(wt)
                        removed = subprocess.run(args,cwd=os.getcwd(),text=True,capture_output=True)
                        if removed.returncode: fail(f"failed step: remove worktree {wt}: {removed.stderr.strip()}")
                    else:
                        pruned = subprocess.run(["git","worktree","prune"],cwd=os.getcwd(),text=True,capture_output=True)
                        if pruned.returncode: fail(f"failed step: prune missing worktree: {pruned.stderr.strip()}")
                agent["created"].remove(f"worktree:{ws}"); save_registry(registry_path(),d)
            if preserved_workspace and f"branch:{agent['branch']}" in agent.get("created",[]):
                agent["created"].remove(f"branch:{agent['branch']}"); save_registry(registry_path(),d)
            if f"branch:{agent['branch']}" in agent.get("created",[]):
                ref=f"refs/heads/{agent['branch']}"
                exists=subprocess.run(["git","show-ref","--verify","--quiet",ref],cwd=os.getcwd(),capture_output=True)
                if exists.returncode not in (0,1): fail(f"failed step: check branch {agent['branch']}: exit {exists.returncode}")
                if exists.returncode == 0:
                    p=subprocess.run(["git","branch","-D" if a.discard else "-d",agent["branch"]],cwd=os.getcwd(),text=True,capture_output=True)
                    if p.returncode:
                        exists=subprocess.run(["git","show-ref","--verify","--quiet",ref],cwd=os.getcwd(),capture_output=True)
                        if exists.returncode != 1: fail(f"failed step: remove branch {agent['branch']}: {p.stderr.strip()}")
                agent["created"].remove(f"branch:{agent['branch']}"); save_registry(registry_path(),d)
        if proof_row(agent) and not wt and PROOF_NAME.fullmatch(agent["name"]):
            shutil.rmtree(checked_proof_dir(agent),ignore_errors=True)
        agent.setdefault("closed_at", time.time()); agent.update(state="closed",status="closed"); deliver(d)
def deregister():
    require_runtime(); key=session_key(os.environ["HERDR_PANE_ID"])
    with locked() as d:
        if key not in d["orchs"]: fail("caller is not a registered orch")
        d["orchs"][key]["gone"]=True; deliver(d)
def parser():
    import argparse
    p=argparse.ArgumentParser(prog="orch"); sub=p.add_subparsers(dest="command",required=True)
    b=sub.add_parser("board",help="show the orch board"); b.add_argument("--once",action="store_true"); b.add_argument("--width",type=int)
    r=sub.add_parser("register"); r.add_argument("--name")
    s=sub.add_parser("spawn"); s.add_argument("name"); s.add_argument("--role",required=True,choices=["plan","build","review","explore"]); s.add_argument("--kind",required=True,choices=["claude","codex"]); s.add_argument("--model"); s.add_argument("--effort"); s.add_argument("--where",required=True,choices=["pane","tab","worktree"]); s.add_argument("--writes",action="store_true"); s.add_argument("--base"); s.add_argument("--brief",required=True,type=Path); s.add_argument("--test-cmd")
    ad=sub.add_parser("adopt"); ad.add_argument("target"); ad.add_argument("--role",choices=["plan","build","review","explore"]); ad.add_argument("--name")
    l=sub.add_parser("list"); l.add_argument("--all",action="store_true"); l.add_argument("--idle",action="store_true"); l.add_argument("--role",choices=["plan","build","review","explore"])
    c=sub.add_parser("close"); c.add_argument("name"); c.add_argument("--keep-checkout",action="store_true"); c.add_argument("--discard",action="store_true")
    v=sub.add_parser("verify",help="check a worker's proof"); v.add_argument("name"); v.add_argument("--against",type=Path); v.add_argument("--want",choices=["REPRODUCED","NOT-REPRODUCED"],default="REPRODUCED")
    sub.add_parser("fingerprint",help="print the hash of this checkout's current state")
    sub.add_parser("deregister"); rs=sub.add_parser("resume"); rs.add_argument("--name"); return p
def main(argv=None):
    a=parser().parse_args(argv)
    if a.command=="board": raise SystemExit(board_command(a))
    elif a.command=="register": register(a.name)
    elif a.command=="spawn": spawn(a)
    elif a.command=="adopt": adopt(a)
    elif a.command=="list": list_agents(a)
    elif a.command=="close": close_agent(a)
    elif a.command=="verify": verify(a)
    elif a.command=="fingerprint": fingerprint_command()
    elif a.command=="deregister": deregister()
    elif a.command=="resume": resume(a.name)
if __name__=="__main__": main()
