#!/usr/bin/env python3
"""Core orch registry and Herdr helpers (Python 3.11+)."""
from __future__ import annotations
import fcntl, json, os, subprocess, sys, tempfile, time, tomllib
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
def spawn(a):
    require_runtime(); project,tree=project_and_tree(); a.writes |= a.where=="worktree"; key=session_key(a.name); orch=session_key(os.environ["HERDR_PANE_ID"]); created=[]
    with locked() as d:
        require_registered(d)
        if key in d["agents"] and d["agents"][key].get("state") in ("starting","live","cleanup","closing"): fail(f"agent already exists: {a.name}")
        live=herdr("agent","list",check=False) or {}
        if a.name in agent_names(live): fail(f"agent already exists in Herdr: {a.name}")
        destination=tree if a.where!="worktree" else str((Path(project)/f"../{Path(project).name}.wt/{a.name}").resolve())
        if a.writes and any(x.get("tree")==destination and x.get("writes") and x.get("state") in ("starting","live","cleanup","closing") for x in d["agents"].values()): fail(f"writer already active in tree: {destination}")
        d["agents"][key]={"name":a.name,"pane":None,"orch":orch,"project":project,"kind":a.kind,"model":a.model,"effort":a.effort,"where":a.where,"writes":bool(a.writes),"tree":destination,"branch":f"orch/{a.name}" if a.where=="worktree" else None,"worktree":None,"role":a.role,"created":created,"state":"starting","status":"starting","since":int(time.time()),"started":False,"stopped":False,"agent_closed":False,"pane_closed":False}
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
            d["agents"][key]["pane"]=pane
            save_registry(registry_path(),d)
            argv=["agent","start",a.name,"--kind",a.kind,"--pane",pane,"--"]
            if a.kind=="claude":
                if a.model: argv += ["--model",a.model]
                if a.effort: argv += ["--effort",a.effort]
            else:
                if a.model: argv += ["-m",a.model]
                if a.effort: argv += ["-c",f"model_reasoning_effort={a.effort}"]
            herdr(*argv); d["agents"][key]["started"]=True; save_registry(registry_path(),d); herdr("agent","prompt",a.name,a.brief.read_text()); d["agents"][key].update(state="live",status="working"); deliver(d)
        except BaseException as exc:
            for item in [x for x in reversed(created) if not x.startswith("branch:")]+[x for x in reversed(created) if x.startswith("branch:")]:
                kind,ident=item.split(":",1)
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
        response=herdr("agent","get",a.target,check=False)
        info=result(response,"result","agent")
        name=info.get("name"); pane=info.get("pane_id")
        kind=info.get("agent") or info.get("kind"); status=info.get("agent_status") or info.get("status")
        if not name or not pane or not kind or not status: fail(f"unknown agent or pane: {a.target}")
        adopted_name=a.name or name
        prefix=os.environ["HERDR_SESSION"]+"/"; key=session_key(adopted_name)
        conflicts=[(old_key,entry) for old_key,entry in d["agents"].items() if old_key.startswith(prefix) and (old_key==key or entry.get("pane")==pane or entry.get("name")==adopted_name)]
        tombstones=[]; idempotent=None
        for old_key,entry in conflicts:
            same_pane=entry.get("pane")==pane
            if (old_key==key or entry.get("name")==adopted_name) and not same_pane:
                fail(f"agent name already in use in this session: {adopted_name}")
            if not same_pane:
                continue
            if entry.get("adopted") and entry.get("state")=="closed":
                tombstones.append(old_key)
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
            entry.update(project=project,tree=tree,kind=kind,model=info.get("model") or "",role=a.role or entry.get("role","explore"),where="adopted",state="live",status=status,created=[],started=False,stopped=False,agent_closed=False,pane_closed=False)
            deliver(d)
            return
        for old_key in tombstones:
            d["agents"].pop(old_key,None)
        d["agents"][key]={"name":adopted_name,"pane":pane,"orch":owner,"project":project,"kind":kind,"model":info.get("model") or "","effort":None,"where":"adopted","writes":False,"tree":tree,"branch":None,"worktree":None,"role":a.role or "explore","created":[],"state":"live","status":status,"since":int(time.time()),"started":False,"stopped":False,"agent_closed":False,"pane_closed":False,"adopted":True}
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
        rows=[x for x in d["agents"].values() if (a.all or x.get("orch")==who) and (not a.idle or x.get("status")=="idle") and (not a.role or x.get("role")==a.role)]
        for x in sorted(rows,key=lambda x:(x.get("role",""),x.get("name",""))): print(f"{x.get('role','?')}\t{x.get('name','?')}\t{x.get('status','unknown')}\t{x.get('where','?')}")
        deliver(d)
def verify_worktree_close(agent, wt):
    target = subprocess.run(["git","rev-parse","HEAD"],cwd=os.getcwd(),text=True,capture_output=True)
    if target.returncode: fail(f"close refused; cannot resolve merge target: {target.stderr.strip()}")
    target = target.stdout.strip()
    refs = [("registered branch", agent["branch"])]
    checkout = subprocess.run(["git","-C",wt,"rev-parse","HEAD"],text=True,capture_output=True)
    if checkout.returncode: fail(f"close refused; cannot read worktree HEAD: {checkout.stderr.strip()}")
    refs.append(("worktree HEAD", checkout.stdout.strip()))
    unmerged = []
    for label, ref in refs:
        merged = subprocess.run(["git","merge-base","--is-ancestor",ref,target],cwd=os.getcwd(),capture_output=True)
        if merged.returncode:
            commits = subprocess.run(["git","log","--oneline",f"{target}..{ref}"],cwd=os.getcwd(),text=True,capture_output=True)
            unmerged.append(f"{label}: {commits.stdout.strip() or ref}")
    status = subprocess.run(["git","-C",wt,"status","--porcelain","--ignored"],text=True,capture_output=True)
    if unmerged or status.returncode or status.stdout:
        fail(f"close refused; unmerged commits: {'; '.join(unmerged) or '(none)'}; dirty paths: {status.stdout.strip() or '(none)'}")
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
        if agent.get("state")=="closed":
            agent["state"]="cleanup"; agent["agent_closed"]=True
        wt=agent.get("worktree")
        if wt and Path(wt).exists() and not a.discard:
            verify_worktree_close(agent, wt)
        agent.update(state="closing",status="closing"); save_registry(registry_path(),d)
        if agent.get("started") and not agent.get("stopped") and not agent.get("agent_closed"):
            herdr("agent","send-keys",a.name,"ctrl+c"); agent["stopped"]=True; save_registry(registry_path(),d)
        if wt and Path(wt).exists() and not a.discard:
            verify_worktree_close(agent, wt)
        for item in reversed(agent.get("created",[])):
            kind,ident=item.split(":",1)
            if kind not in ("pane","tab","workspace"): continue
            if herdr(kind,"close",ident,check=False) is None: fail(f"failed step: close {kind} {ident}")
            agent["created"].remove(item); save_registry(registry_path(),d)
        if any(item.startswith(("pane:","tab:","workspace:")) for item in agent.get("created",[])):
            fail(f"failed step: cleanup remains for {a.name}: {', '.join(agent['created'])}")
        if wt and not a.keep_checkout:
            ws=next((x.split(":",1)[1] for x in agent.get("created",[]) if x.startswith("worktree:")),None)
            if ws:
                missing = False
                if wt and Path(wt).exists():
                    result = herdr("worktree","remove","--workspace",ws,check=False,return_errors=True)
                    error = result.get("error") if isinstance(result, dict) else None
                    missing = isinstance(error, dict) and error.get("code") == "workspace_not_found"
                    if error and not missing: fail(f"herdr worktree remove --workspace {ws} failed: {error.get('message', error)}")
                    if result is None: fail(f"herdr worktree remove --workspace {ws} failed")
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
            if f"branch:{agent['branch']}" in agent.get("created",[]):
                p=subprocess.run(["git","branch","-D" if a.discard else "-d",agent["branch"]],cwd=os.getcwd(),text=True,capture_output=True)
                if p.returncode: fail(f"failed step: remove branch {agent['branch']}: {p.stderr.strip()}")
                agent["created"].remove(f"branch:{agent['branch']}"); save_registry(registry_path(),d)
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
    s=sub.add_parser("spawn"); s.add_argument("name"); s.add_argument("--role",required=True,choices=["plan","build","review","explore"]); s.add_argument("--kind",required=True,choices=["claude","codex"]); s.add_argument("--model"); s.add_argument("--effort"); s.add_argument("--where",required=True,choices=["pane","tab","worktree"]); s.add_argument("--writes",action="store_true"); s.add_argument("--base"); s.add_argument("--brief",required=True,type=Path)
    ad=sub.add_parser("adopt"); ad.add_argument("target"); ad.add_argument("--role",choices=["plan","build","review","explore"]); ad.add_argument("--name")
    l=sub.add_parser("list"); l.add_argument("--all",action="store_true"); l.add_argument("--idle",action="store_true"); l.add_argument("--role",choices=["plan","build","review","explore"])
    c=sub.add_parser("close"); c.add_argument("name"); c.add_argument("--keep-checkout",action="store_true"); c.add_argument("--discard",action="store_true")
    sub.add_parser("deregister"); rs=sub.add_parser("resume"); rs.add_argument("--name"); return p
def main(argv=None):
    a=parser().parse_args(argv)
    if a.command=="board": raise SystemExit(board_command(a))
    elif a.command=="register": register(a.name)
    elif a.command=="spawn": spawn(a)
    elif a.command=="adopt": adopt(a)
    elif a.command=="list": list_agents(a)
    elif a.command=="close": close_agent(a)
    elif a.command=="deregister": deregister()
    elif a.command=="resume": resume(a.name)
if __name__=="__main__": main()
