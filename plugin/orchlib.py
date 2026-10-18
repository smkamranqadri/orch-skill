#!/usr/bin/env python3
"""Core orch registry and Herdr helpers (Python 3.11+)."""
from __future__ import annotations
import fcntl, json, os, subprocess, sys, tempfile, time
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
def herdr(*args,check=True,missing_workspace_ok=False,return_errors=False):
    p=subprocess.run(["herdr",*map(str,args)],text=True,capture_output=True)
    if check and p.returncode:
        error=(p.stderr or p.stdout).strip()
        if missing_workspace_ok and args[:3]==("pane","list","--workspace") and "workspace not found" in error.lower(): return {"missing_workspace":True}
        fail(f"herdr {' '.join(map(str,args))} failed: {error}")
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
def deliver(data):
    session=os.environ["HERDR_SESSION"] + "/"
    for key,orch in data["orchs"].items():
        if not key.startswith(session): continue
        if orch.get("gone") or not orch.get("queue"): continue
        live=herdr("agent","get",orch["pane"],check=False) or {}
        live_agent=result(live,"result","agent")
        status=live_agent.get("agent_status") or live_agent.get("status") or result(live,"result").get("agent_status") or result(live,"result").get("status") or "unknown"
        if status not in ("idle","done"): continue
        message="\n".join(orch["queue"])
        if herdr("agent","prompt",orch["pane"],message,check=False) is not None:
            orch["queue"].clear(); orch["status"]="working"
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
def workspace():
    v=os.environ.get("HERDR_WORKSPACE_ID")
    if not v: fail("HERDR_WORKSPACE_ID is required")
    return v
def register(name=None):
    require_runtime(); project,_=project_and_tree(); pane=os.environ["HERDR_PANE_ID"]; key=session_key(pane); name=name or "orch"
    with locked() as d:
        if key in d["orchs"] and not d["orchs"][key].get("gone"):
            deliver(d); return
        session=os.environ["HERDR_SESSION"] + "/"
        for old_key,entry in d["orchs"].items():
            if not old_key.startswith(session) or entry.get("project")!=project or entry.get("gone"): continue
            listing=herdr("pane","list","--workspace",entry["workspace"],missing_workspace_ok=True)
            if listing.get("missing_workspace") or entry.get("pane") not in pane_ids(listing): entry["gone"]=True
        if key in d["orchs"]:
            d["orchs"][key].update({"project":project,"name":name,"kind":os.environ.get("ORCH_KIND","claude"),"pane":pane,"workspace":workspace(),"tab":os.environ.get("HERDR_TAB_ID",""),"status":"idle","gone":False})
        else:
            d["orchs"][key]={"project":project,"name":name,"kind":os.environ.get("ORCH_KIND","claude"),"pane":pane,"workspace":workspace(),"tab":os.environ.get("HERDR_TAB_ID",""),"status":"idle","gone":False,"queue":[]}
        orphaned=[a for agent_key,a in d["agents"].items() if agent_key.startswith(session) and a.get("project")==project and a.get("orch","").startswith(session) and d["orchs"].get(a.get("orch"),{}).get("gone")]
        old_owners={a.get("orch") for a in orphaned}
        for old_key in old_owners:
            d["orchs"][key]["queue"].extend(d["orchs"][old_key].get("queue",[]))
            d["orchs"][old_key]["queue"].clear()
        for agent in orphaned:
            agent["orch"]=key
            d["orchs"][key]["queue"].append(f"[orch] {agent['name']} {agent.get('status','unknown')} · pane {agent.get('pane','?')} · read: herdr agent read {agent['name']}")
        opened=herdr("plugin","pane","open","--plugin","orch","--entrypoint","board","--placement","split","--target-pane",pane,"--direction","right","--cwd",project,check=False)
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
        d["agents"][key]={"name":a.name,"pane":None,"orch":orch,"project":project,"kind":a.kind,"model":a.model,"effort":a.effort,"where":a.where,"writes":bool(a.writes),"tree":destination,"branch":f"orch/{a.name}" if a.where=="worktree" else None,"worktree":None,"role":a.role,"created":created,"state":"starting","status":"starting","since":int(time.time()),"started":False,"stopped":False}
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
                out=herdr("worktree","create","--workspace",workspace(),"--cwd",project,"--branch",f"orch/{a.name}","--base",a.base or "HEAD","--path",f"../{Path(project).name}.wt/{a.name}","--label",a.name,"--no-focus"); pane=result(out,"result","root_pane").get("pane_id"); ws=result(out,"result","workspace").get("workspace_id"); wt=result(out,"result","worktree").get("path") or f"../{Path(project).name}.wt/{a.name}"
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
                elif kind in ("pane","tab","workspace"): ok=herdr(kind,"close","--"+kind,ident,check=False) is not None
                elif kind=="branch":
                    p=subprocess.run(["git","branch","-d",ident],cwd=project,text=True,capture_output=True); ok=p.returncode==0
                if not ok: break
                created.remove(item); save_registry(registry_path(),d)
            if not created: d["agents"].pop(key,None)
            else: d["agents"][key].update(state="cleanup",status="cleanup")
            if isinstance(exc,SystemExit): raise
            fail(f"failed step: spawn {a.name}: {exc}")
def list_agents(a):
    require_runtime(); who=session_key(os.environ["HERDR_PANE_ID"])
    with locked() as d:
        require_registered(d)
        rows=[x for x in d["agents"].values() if (a.all or x.get("orch")==who) and (not a.idle or x.get("status")=="idle") and (not a.role or x.get("role")==a.role)]
        for x in sorted(rows,key=lambda x:(x.get("role",""),x.get("name",""))): print(f"{x.get('role','?')}\t{x.get('name','?')}\t{x.get('status','unknown')}\t{x.get('where','?')}")
        deliver(d)
def close_agent(a):
    require_runtime()
    with locked() as d:
        require_registered(d)
        key=session_key(a.name); agent=d["agents"].get(key)
        if not agent: fail(f"unknown agent: {a.name}")
        if agent.get("state")=="closed":
            deliver(d); return
        wt=agent.get("worktree")
        if wt and Path(wt).exists() and not a.discard:
            base=subprocess.run(["git","merge-base","--is-ancestor",agent["branch"],"HEAD"],cwd=os.getcwd(),capture_output=True)
            status=subprocess.run(["git","-C",wt,"status","--porcelain","--ignored"],text=True,capture_output=True)
            if base.returncode or status.returncode or status.stdout:
                log=subprocess.run(["git","log","--oneline",f"HEAD..{agent['branch']}"],text=True,capture_output=True).stdout.strip()
                fail(f"close refused; unmerged commits: {log or '(none)'}; dirty paths: {status.stdout.strip() or '(none)'}")
        agent["state"]="closing"; save_registry(registry_path(),d)
        if agent.get("started") and not agent.get("stopped"):
            herdr("agent","send-keys",a.name,"ctrl+c"); agent["stopped"]=True; save_registry(registry_path(),d)
        for item in reversed(agent.get("created",[])):
            kind,ident=item.split(":",1)
            if kind not in ("pane","tab","workspace"): continue
            if herdr(kind,"close","--"+kind,ident,check=False) is None: fail(f"failed step: close {kind} {ident}")
            agent["created"].remove(item); save_registry(registry_path(),d)
        if any(item.startswith(("pane:","tab:","workspace:")) for item in agent.get("created",[])):
            fail(f"failed step: cleanup remains for {a.name}: {', '.join(agent['created'])}")
        if wt and not a.keep_checkout:
            ws=next((x.split(":",1)[1] for x in agent.get("created",[]) if x.startswith("worktree:")),None)
            if ws:
                herdr("worktree","remove","--workspace",ws); agent["created"].remove(f"worktree:{ws}"); save_registry(registry_path(),d)
            if f"branch:{agent['branch']}" in agent.get("created",[]):
                p=subprocess.run(["git","branch","-D" if a.discard else "-d",agent["branch"]],cwd=os.getcwd(),text=True,capture_output=True)
                if p.returncode: fail(f"failed step: remove branch {agent['branch']}: {p.stderr.strip()}")
                agent["created"].remove(f"branch:{agent['branch']}"); save_registry(registry_path(),d)
        agent.update(state="closed",status="closed"); deliver(d)
def deregister():
    require_runtime(); key=session_key(os.environ["HERDR_PANE_ID"])
    with locked() as d:
        if key not in d["orchs"]: fail("caller is not a registered orch")
        d["orchs"][key]["gone"]=True; deliver(d)
def parser():
    import argparse
    p=argparse.ArgumentParser(prog="orch"); sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("register"); r.add_argument("--name")
    s=sub.add_parser("spawn"); s.add_argument("name"); s.add_argument("--role",required=True,choices=["plan","build","review","explore"]); s.add_argument("--kind",required=True,choices=["claude","codex"]); s.add_argument("--model"); s.add_argument("--effort"); s.add_argument("--where",required=True,choices=["pane","tab","worktree"]); s.add_argument("--writes",action="store_true"); s.add_argument("--base"); s.add_argument("--brief",required=True,type=Path)
    l=sub.add_parser("list"); l.add_argument("--all",action="store_true"); l.add_argument("--idle",action="store_true"); l.add_argument("--role",choices=["plan","build","review","explore"])
    c=sub.add_parser("close"); c.add_argument("name"); c.add_argument("--keep-checkout",action="store_true"); c.add_argument("--discard",action="store_true")
    sub.add_parser("deregister"); return p
def main(argv=None):
    a=parser().parse_args(argv)
    if a.command=="register": register(a.name)
    elif a.command=="spawn": spawn(a)
    elif a.command=="list": list_agents(a)
    elif a.command=="close": close_agent(a)
    elif a.command=="deregister": deregister()
if __name__=="__main__": main()
