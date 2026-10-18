import json, os, pathlib, shutil, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
CLI=ROOT/'plugin'/'orch'
class PhaseOne(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name)
  self.home=self.root/'state'; self.home.mkdir(); self.userhome=self.root/'home'; self.userhome.mkdir(); self.bin=self.root/'bin'; self.bin.mkdir(); self.log=self.root/'calls.jsonl'; self.resources=self.home/'herdr-resources.json'; self.resources.write_text(json.dumps({'panes':{},'tabs':{}}))
  scrubbed=os.environ.copy()
  for name in ('FAIL_START','FAIL_PROMPT','FAIL_CLOSE','FAIL_WORKTREE_REMOVE','LIVE_AGENT','CHECK_RESOURCE','CHECK_RESERVATION'):
   scrubbed.pop(name,None)
  self.env=scrubbed|{'HOME':str(self.userhome),'GIT_CONFIG_GLOBAL':str(self.userhome/'gitconfig'),'GIT_CONFIG_SYSTEM':os.devnull,'XDG_CONFIG_HOME':str(self.userhome/'config'),'PATH':str(self.bin)+os.pathsep+scrubbed['PATH'],'XDG_STATE_HOME':str(self.home),'CALLS':str(self.log),'HERDR_ENV':'1','HERDR_SESSION':'session-a','HERDR_PANE_ID':'p1','HERDR_WORKSPACE_ID':'ws1','HERDR_TAB_ID':'tab1'}
  fake=self.bin/'herdr'
  fake.write_text('''#!/usr/bin/env python3
import json,os,sys,subprocess,shutil
args=sys.argv[1:]
resource_file=os.path.join(os.environ["XDG_STATE_HOME"],"herdr-resources.json")
def load_resources(): return json.load(open(resource_file))
def save_resources(value): json.dump(value,open(resource_file,"w"))
with open(os.environ["CALLS"],"a") as f:f.write(json.dumps(args)+"\\n")
if args[:2]==["agent","start"] and os.environ.get("CHECK_RESOURCE"):
 d=json.load(open(os.path.join(os.environ["XDG_STATE_HOME"],"orch","registry.json")))
 entry=d["agents"].get(os.environ["HERDR_SESSION"]+"/"+args[2],{})
 ok=entry.get("state")=="starting" and entry.get("pane")=="newpane" and "pane:newpane" in entry.get("created",[])
 open(os.environ["CHECK_RESOURCE"],"w").write("yes" if ok else "no")
 if not ok: sys.exit(4)
if os.environ.get("FAIL_START")=="1" and args[:2]==["agent","start"]: print("simulated failure",file=sys.stderr); sys.exit(3)
if args[:2] in (["pane","close"],["tab","close"],["workspace","close"]) and os.environ.get("FAIL_CLOSE")==args[-1]: print("simulated close failure",file=sys.stderr); sys.exit(3)
if args[:2]==["pane","list"]: print(json.dumps({"result":{"panes":[{"pane_id":"p1"}]}}))
elif args[:2]==["pane","layout"]: print(json.dumps({"result":{"pane":{"width":120,"height":40}}}))
elif args[:2]==["pane","split"]:
 if os.environ.get("CHECK_RESERVATION"):
  d=json.load(open(os.path.join(os.environ["XDG_STATE_HOME"],"orch","registry.json"))); entry=d["agents"].get(os.environ["HERDR_SESSION"]+"/reserved",{})
  ok=entry.get("state")=="starting" and entry.get("created")==[]
  open(os.environ["CHECK_RESERVATION"],"w").write("yes" if ok else "no")
  if not ok: sys.exit(4)
 r=load_resources(); r['panes']['newpane']=None; save_resources(r)
 print(json.dumps({"result":{"pane":{"pane_id":"newpane"}}}))
elif args[:2]==["tab","create"]:
 r=load_resources(); r['tabs']['newtab']=['tabpane']; r['panes']['tabpane']='newtab'; save_resources(r)
 print(json.dumps({"result":{"root_pane":{"pane_id":"tabpane"},"tab":{"tab_id":"newtab"}}}))
elif args[:2]==["pane","close"]:
 ident=args[-1]; r=load_resources()
 if ident not in r['panes']: print("pane not found",file=sys.stderr); sys.exit(3)
 parent=r['panes'].pop(ident)
 if parent in r['tabs']: r['tabs'][parent].remove(ident)
 save_resources(r); print(json.dumps({"result":{}}))
elif args[:2]==["tab","close"]:
 ident=args[-1]; r=load_resources()
 if ident not in r['tabs']: print("tab not found",file=sys.stderr); sys.exit(3)
 for child in r['tabs'].pop(ident): r['panes'].pop(child,None)
 save_resources(r); print(json.dumps({"result":{}}))
elif args[:2]==["worktree","create"]:
 cwd=args[args.index("--cwd")+1]; branch=args[args.index("--branch")+1]; base=args[args.index("--base")+1]; path=args[args.index("--path")+1]
 subprocess.run(["git","-C",cwd,"worktree","add","-qb",branch,path,base],check=True)
 open(os.path.join(os.environ["XDG_STATE_HOME"],"wtws-path"),"w").write(os.path.realpath(os.path.join(cwd,path)))
 print(json.dumps({"result":{"root_pane":{"pane_id":"wtpane"},"workspace":{"workspace_id":"wtws"},"worktree":{"path":path}}}))
elif args[:2]==["worktree","remove"]:
 if os.environ.get("FAIL_WORKTREE_REMOVE")=="1": print("simulated remove failure",file=sys.stderr); sys.exit(3)
 path=open(os.path.join(os.environ["XDG_STATE_HOME"],"wtws-path")).read()
 shutil.rmtree(path)
 subprocess.run(["git","-C",os.getcwd(),"worktree","prune"],check=True)
 print(json.dumps({"result":{}}))
elif args[:2]==["plugin","pane"]: print(json.dumps({"result":{"pane":{"pane_id":"board"}}}))
elif args[:2]==["agent","list"]: print(json.dumps({"result":{"agents":[{"name":os.environ["LIVE_AGENT"]}] if os.environ.get("LIVE_AGENT") else []}}))
elif args[:2]==["agent","get"]: print(json.dumps({"result":{"agent":{"status":os.environ.get("ORCH_STATUS","idle")}}}))
elif args[:2]==["agent","prompt"] and os.environ.get("FAIL_PROMPT")=="1": print("prompt failed",file=sys.stderr); sys.exit(2)
else: print(json.dumps({"result":{}}))
'''); fake.chmod(0o755)
  self.repo=self.root/'repo'; self.repo.mkdir(); subprocess.run(['git','init','-q',str(self.repo)],check=True,env=self.env); subprocess.run(['git','-C',str(self.repo),'config','user.email','test@example.invalid'],check=True,env=self.env); subprocess.run(['git','-C',str(self.repo),'config','user.name','Fictional Tester'],check=True,env=self.env)
  (self.repo/'seed.txt').write_text('seed\n'); subprocess.run(['git','-C',str(self.repo),'add','seed.txt'],check=True,env=self.env); subprocess.run(['git','-C',str(self.repo),'commit','-qm','seed'],check=True,env=self.env)
 def tearDown(self): self.tmp.cleanup()
 def runcli(self,*args,ok=True,env=None,cwd=None):
  p=subprocess.run([str(CLI),*args],cwd=cwd or self.repo,env=env or self.env,text=True,capture_output=True)
  if ok: self.assertEqual(p.returncode,0,p.stderr)
  else: self.assertNotEqual(p.returncode,0,p.stdout)
  return p
 def calls(self): return [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []
 def state(self): return json.loads((self.home/'orch/registry.json').read_text())
 def reg(self,pane='p1',session='session-a',cwd=None):
  e=self.env|{'HERDR_PANE_ID':pane,'HERDR_SESSION':session}; self.runcli('register',env=e,cwd=cwd)
 def spawn(self,name='worker',where='pane',kind='claude',extra=()):
  brief=self.root/'brief.txt'; brief.write_text('Build fictional widget')
  return self.runcli('spawn',name,'--role','build','--kind',kind,'--where',where,'--brief',str(brief),*extra)
 def test_two_registers_idempotence_adoption_and_sessions(self):
  self.reg(); self.assertIn(['plugin','pane','open','--plugin','orch','--entrypoint','board','--placement','split','--target-pane','p1','--direction','right','--cwd',str(self.repo)],self.calls()); before=len(self.calls()); self.reg(); self.assertEqual(len(self.calls()),before)
  self.reg('p2'); self.reg('p3','session-b'); d=self.state(); self.assertEqual(len(d['orchs']),3); self.assertIn('session-a/p1',d['orchs']); self.assertIn('session-a/p2',d['orchs']); self.assertIn('session-b/p3',d['orchs'])
 def test_liveness_reconcile_marks_missing_orch_gone(self):
  self.reg(); d=self.state(); d['orchs']['session-a/missing']={'project':str(self.repo),'pane':'p9','workspace':'ws-old','gone':False,'queue':[]}; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.reg('p2'); self.assertTrue(self.state()['orchs']['session-a/missing']['gone'])
 def test_linked_worktree_project_resolution(self):
  wt=self.root/'linked'; subprocess.run(['git','-C',str(self.repo),'worktree','add','-qb','linked',str(wt)],check=True,env=self.env)
  self.reg('p1','linked-session',cwd=wt); self.assertEqual(self.state()['orchs']['linked-session/p1']['project'],str(self.repo))
 def test_register_reconcile_adopts_queue_and_notices(self):
  self.reg(); d=self.state(); d['orchs']['session-a/p1']['gone']=True; d['orchs']['session-a/p1']['queue']=['old queued item']; d['agents']['session-a/ghost']={'name':'ghost','orch':'session-a/p1','project':str(self.repo),'pane':'p9','status':'done'}; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('register',env=self.env|{'HERDR_PANE_ID':'p2','ORCH_STATUS':'working'}); d=self.state(); self.assertEqual(d['agents']['session-a/ghost']['orch'],'session-a/p2'); self.assertEqual(d['orchs']['session-a/p2']['queue'][0],'old queued item'); self.assertEqual(d['orchs']['session-a/p2']['queue'][1],'[orch] ghost done · pane p9 · read: herdr agent read ghost')
 def test_session_isolates_delivery_reconcile_and_adoption(self):
  self.reg(); d=self.state(); d['orchs']['session-b/p1']={'project':str(self.repo),'pane':'p1','workspace':'wsB','gone':False,'queue':['foreign queue']}; d['agents']['session-b/ghost']={'name':'ghost','orch':'session-b/p1','project':str(self.repo),'pane':'p9','status':'done'}; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('register',env=self.env|{'HERDR_SESSION':'session-a','HERDR_PANE_ID':'p2'})
  d=self.state(); self.assertEqual(d['orchs']['session-b/p1']['queue'],['foreign queue']); self.assertFalse(d['orchs']['session-b/p1']['gone']); self.assertEqual(d['agents']['session-b/ghost']['orch'],'session-b/p1')
  self.assertNotIn(['agent','prompt','p1','foreign queue'],self.calls()); self.assertFalse(any(c[:3]==['pane','list','--workspace'] and c[-1]=='wsB' for c in self.calls()))
 def test_foreign_session_orphan_is_not_adopted(self):
  self.reg(); d=self.state(); d['orchs']['session-b/p1']={'project':str(self.repo),'pane':'p1','workspace':'wsB','gone':True,'queue':['foreign']}; d['agents']['session-b/ghost']={'name':'ghost','orch':'session-b/p1','project':str(self.repo),'pane':'p9','status':'done'}; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('register',env=self.env|{'HERDR_PANE_ID':'p2'}); d=self.state(); self.assertEqual(d['agents']['session-b/ghost']['orch'],'session-b/p1'); self.assertEqual(d['orchs']['session-b/p1']['queue'],['foreign'])
 def test_reregister_reactivates_gone_and_adopts(self):
  self.reg(); d=self.state(); d['orchs']['session-a/p1']['gone']=True; d['agents']['session-a/ghost']={'name':'ghost','orch':'session-a/p1','project':str(self.repo),'pane':'p9','status':'done'}; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('register'); d=self.state(); self.assertFalse(d['orchs']['session-a/p1']['gone']); self.assertEqual(d['agents']['session-a/ghost']['orch'],'session-a/p1')
 def test_spawn_locations_flags_host_argv_and_role(self):
  self.reg(); self.spawn(extra=('--model','sonnet-fake','--effort','medium')); c=self.calls()
  self.assertIn(['pane','split','--pane','p1','--direction','right','--cwd',str(self.repo),'--no-focus'],c)
  self.assertIn(['agent','start','worker','--kind','claude','--pane','newpane','--','--model','sonnet-fake','--effort','medium'],c)
  d=self.state()['agents']['session-a/worker']; self.assertEqual(d['role'],'build'); self.assertEqual(d['state'],'live')
  self.spawn('tabber','tab','codex',('--model','fake-codex','--effort','low')); c=self.calls()
  self.assertIn(['tab','create','--workspace','ws1','--cwd',str(self.repo),'--label','tabber','--no-focus'],c)
  self.assertIn(['agent','start','tabber','--kind','codex','--pane','tabpane','--','-m','fake-codex','-c','model_reasoning_effort=low'],c)
 def test_worktree_spawn_and_writer_refusal(self):
  self.reg(); self.spawn('writer','worktree'); d=self.state()['agents']['session-a/writer']; self.assertTrue(d['writes']); self.assertEqual(d['branch'],'orch/writer')
  self.assertIn(['worktree','create','--workspace','ws1','--cwd',str(self.repo),'--branch','orch/writer','--base','HEAD','--path','../repo.wt/writer','--label','writer','--no-focus'],self.calls())
  self.spawn('writer2','pane',extra=('--writes',))
  self.runcli('spawn','writer3','--role','build','--kind','claude','--where','pane','--writes','--brief',str(self.root/'brief.txt'),ok=False)
 def test_duplicate_live_herdr_agent_name_refused_exactly(self):
  self.reg(); (self.root/'brief.txt').write_text('Build fictional widget'); e=self.env|{'LIVE_AGENT':'occupied'}
  p=self.runcli('spawn','occupied','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False,env=e)
  self.assertEqual(p.stderr.strip(),'orch: agent already exists in Herdr: occupied')
  self.runcli('spawn','occupied-extra','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),env=e)
 def test_parallel_writers_same_tree_allow_only_one(self):
  self.reg(); brief=self.root/'brief.txt'; brief.write_text('Build fictional component')
  procs=[subprocess.Popen([str(CLI),'spawn',name,'--role','build','--kind','claude','--where','pane','--writes','--brief',str(brief)],cwd=self.repo,env=self.env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for name in ('parallel-one','parallel-two')]
  results=[p.communicate()+(p.returncode,) for p in procs]; self.assertEqual(sorted(r[2] for r in results),[0,1]); self.assertEqual(sum(c[:2]==['agent','start'] for c in self.calls()),1); self.assertEqual(sum(c[:2]==['pane','split'] for c in self.calls()),1); self.assertEqual(sum(a.get('writes') and a.get('state')=='live' for a in self.state()['agents'].values()),1)
 def test_main_writer_and_worktree_writer_reserve_distinct_trees(self):
  self.reg(); self.spawn('main-writer','pane',extra=('--writes',)); self.spawn('isolated-writer','worktree')
  d=self.state()['agents']; self.assertNotEqual(d['session-a/main-writer']['tree'],d['session-a/isolated-writer']['tree'])
  p=self.runcli('spawn','second-main','--role','build','--kind','claude','--where','pane','--writes','--brief',str(self.root/'brief.txt'),ok=False); self.assertIn('writer already active in tree',p.stderr)
 def test_worktree_writer_then_main_writer_are_independent(self):
  self.reg(); self.spawn('isolated-writer','worktree'); self.spawn('main-writer','pane',extra=('--writes',))
 def test_duplicate_and_outside_herdr_errors(self):
  self.reg(); self.spawn(); self.runcli('spawn','worker','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False)
  e=self.env.copy(); del e['HERDR_ENV']; p=self.runcli('list',env=e,ok=False); self.assertEqual(p.stderr.strip(),'orch: must run inside Herdr (HERDR_ENV is unset)')
 def test_fixture_git_environment_is_isolated(self):
  self.assertEqual(self.env['HOME'],str(self.userhome)); self.assertEqual(self.env['GIT_CONFIG_GLOBAL'],str(self.userhome/'gitconfig')); self.assertEqual(self.env['GIT_CONFIG_SYSTEM'],os.devnull)
  self.assertTrue(all(name not in self.env for name in ('FAIL_START','FAIL_PROMPT','FAIL_CLOSE','FAIL_WORKTREE_REMOVE','LIVE_AGENT')))
 def test_list_role_idle_filters(self):
  self.reg(); self.spawn(); self.spawn('working-review','pane'); d=self.state(); d['agents']['session-a/worker']['status']='idle'; d['agents']['session-a/working-review']['role']='build'; (self.home/'orch/registry.json').write_text(json.dumps(d))
  p=self.runcli('list','--idle','--role','build'); self.assertEqual(p.stdout.splitlines(),['build\tworker\tidle\tpane'])
  p=self.runcli('list','--idle','--role','explore'); self.assertEqual(p.stdout,'')
 def test_cli_retries_queue_only_when_orch_is_idle_or_done(self):
  self.reg(); d=self.state(); d['orchs']['session-a/p1']['queue']=['[orch] reviewer done · pane p2 · read: herdr agent read reviewer']; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('list',env=self.env|{'ORCH_STATUS':'working'}); self.assertEqual(self.state()['orchs']['session-a/p1']['queue'],['[orch] reviewer done · pane p2 · read: herdr agent read reviewer'])
  self.runcli('list',env=self.env|{'ORCH_STATUS':'idle'}); self.assertEqual(self.state()['orchs']['session-a/p1']['queue'],[])
  self.assertIn(['agent','prompt','p1','[orch] reviewer done · pane p2 · read: herdr agent read reviewer'],self.calls())
 def test_failed_delivery_keeps_queue(self):
  self.reg(); d=self.state(); d['orchs']['session-a/p1']['queue']=['queued notice']; (self.home/'orch/registry.json').write_text(json.dumps(d))
  self.runcli('list',env=self.env|{'FAIL_PROMPT':'1'},ok=True); self.assertEqual(self.state()['orchs']['session-a/p1']['queue'],['queued notice'])
 def test_unregistered_caller_is_refused(self):
  p=self.runcli('list',ok=False); self.assertEqual(p.stderr.strip(),'orch: caller is not a registered orch')
 def test_deregister_marks_gone(self):
  self.reg(); self.runcli('deregister'); self.assertTrue(self.state()['orchs']['session-a/p1']['gone'])
 def test_start_sees_durable_starting_reservation_and_created_pane(self):
  self.reg(); marker=self.root/'reservation'; (self.root/'brief.txt').write_text('Build fictional widget')
  resource=self.root/'resource'; self.runcli('spawn','reserved','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),env=self.env|{'CHECK_RESERVATION':str(marker),'CHECK_RESOURCE':str(resource)})
  self.assertEqual(marker.read_text(),'yes'); self.assertEqual(resource.read_text(),'yes')
 def test_failed_cleanup_keeps_retryable_reservation(self):
  self.reg(); e=self.env|{'FAIL_START':'1','FAIL_CLOSE':'newpane'}; self.runcli('spawn','broken','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False,env=e)
  agent=self.state()['agents']['session-a/broken']; self.assertEqual(agent['state'],'cleanup'); self.assertEqual(agent['created'],['pane:newpane'])
  self.runcli('close','broken'); self.assertEqual(self.state()['agents']['session-a/broken']['state'],'closed')
 def test_cleanup_reservation_blocks_name_replacement(self):
  self.reg(); self.runcli('spawn','reserved-name','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False,env=self.env|{'FAIL_START':'1','FAIL_CLOSE':'newpane'})
  before=self.state()['agents']['session-a/reserved-name']['created']; calls=self.calls()
  p=self.runcli('spawn','reserved-name','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False)
  self.assertEqual(p.stderr.strip(),'orch: agent already exists: reserved-name'); self.assertEqual(self.state()['agents']['session-a/reserved-name']['created'],before); self.assertEqual(self.calls(),calls)
 def test_cleanup_writer_reservation_blocks_second_writer(self):
  self.reg(); self.runcli('spawn','uncertain-writer','--role','build','--kind','claude','--where','pane','--writes','--brief',str(self.root/'brief.txt'),ok=False,env=self.env|{'FAIL_PROMPT':'1','FAIL_CLOSE':'newpane'})
  old=self.state()['agents']['session-a/uncertain-writer']; self.assertEqual(old['state'],'cleanup'); self.assertTrue(old['started']); self.assertFalse(old['stopped'])
  p=self.runcli('spawn','second-writer','--role','build','--kind','claude','--where','pane','--writes','--brief',str(self.root/'brief.txt'),ok=False)
  self.assertIn('writer already active in tree',p.stderr); self.assertNotIn('session-a/second-writer',self.state()['agents'])
 def test_failed_worktree_rollback_keeps_branch_for_retry(self):
  self.reg(); (self.root/'brief.txt').write_text('Build fictional widget'); e=self.env|{'FAIL_START':'1','FAIL_WORKTREE_REMOVE':'1'}
  self.runcli('spawn','broken-writer','--role','build','--kind','claude','--where','worktree','--brief',str(self.root/'brief.txt'),ok=False,env=e)
  agent=self.state()['agents']['session-a/broken-writer']; self.assertEqual(agent['state'],'cleanup'); self.assertIn('branch:orch/broken-writer',agent['created']); self.assertIn('worktree:wtws',agent['created'])
  branch=subprocess.run(['git','-C',str(self.repo),'branch','--list','orch/broken-writer'],text=True,capture_output=True,env=self.env); self.assertEqual(branch.stdout.strip(),'+ orch/broken-writer')
  self.runcli('close','broken-writer'); self.assertEqual(self.state()['agents']['session-a/broken-writer']['state'],'closed')
  branch=subprocess.run(['git','-C',str(self.repo),'branch','--list','orch/broken-writer'],text=True,capture_output=True,env=self.env); self.assertEqual(branch.stdout,'')
  self.assertNotIn('--force',[arg for call in self.calls() for arg in call])
 def test_partial_close_resumes_successful_steps(self):
  self.reg(); self.spawn('tabber','tab'); self.runcli('close','tabber',ok=False,env=self.env|{'FAIL_CLOSE':'tabpane'})
  a=self.state()['agents']['session-a/tabber']; self.assertEqual(a['created'],['tab:newtab','pane:tabpane']); self.assertTrue(a['stopped'])
  resources=json.loads(self.resources.read_text()); self.assertIn('newtab',resources['tabs']); self.assertIn('tabpane',resources['panes'])
  self.runcli('close','tabber'); self.assertEqual(self.state()['agents']['session-a/tabber']['state'],'closed'); self.assertEqual(self.calls().count(['agent','send-keys','tabber','ctrl+c']),1)
  resources=json.loads(self.resources.read_text()); self.assertNotIn('newtab',resources['tabs']); self.assertNotIn('tabpane',resources['panes'])
 def test_rollback_stops_when_child_close_fails(self):
  self.reg(); self.runcli('spawn','broken-tab','--role','build','--kind','claude','--where','tab','--brief',str(self.root/'brief.txt'),ok=False,env=self.env|{'FAIL_START':'1','FAIL_CLOSE':'tabpane'})
  a=self.state()['agents']['session-a/broken-tab']; self.assertEqual(a['state'],'cleanup'); self.assertEqual(a['created'],['tab:newtab','pane:tabpane'])
  resources=json.loads(self.resources.read_text()); self.assertIn('newtab',resources['tabs']); self.assertIn('tabpane',resources['panes'])
  self.runcli('close','broken-tab'); self.assertEqual(self.state()['agents']['session-a/broken-tab']['state'],'closed')
  resources=json.loads(self.resources.read_text()); self.assertNotIn('newtab',resources['tabs']); self.assertNotIn('tabpane',resources['panes'])
 def test_spawn_failure_rolls_back_created_resources(self):
  self.reg(); e=self.env|{'FAIL_START':'1'}; p=self.runcli('spawn','broken','--role','build','--kind','claude','--where','pane','--brief',str(self.root/'brief.txt'),ok=False,env=e)
  self.assertNotIn('session-a/broken',self.state()['agents']); self.assertIn(['pane','close','--pane','newpane'],self.calls())
 def test_worktree_start_failure_removes_branch_without_force(self):
  self.reg(); (self.root/'brief.txt').write_text('Build fictional widget'); self.runcli('spawn','broken-writer','--role','build','--kind','claude','--where','worktree','--brief',str(self.root/'brief.txt'),ok=False,env=self.env|{'FAIL_START':'1'})
  self.assertNotIn('session-a/broken-writer',self.state()['agents'])
  branch=subprocess.run(['git','-C',str(self.repo),'branch','--list','orch/broken-writer'],text=True,capture_output=True,env=self.env); self.assertEqual(branch.stdout,'')
  self.assertNotIn('--force',[arg for call in self.calls() for arg in call])
 def test_close_worktree_preflight_does_not_stop(self):
  self.reg(); self.spawn('writer','worktree'); wt=pathlib.Path(self.state()['agents']['session-a/writer']['worktree']); (wt/'untracked-fictional.txt').write_text('unsaved')
  n=len(self.calls()); p=self.runcli('close','writer',ok=False); self.assertIn('dirty paths: ?? untracked-fictional.txt',p.stderr); self.assertEqual(len(self.calls()),n)
 def test_close_retry_rechecks_checkout_before_destructive_calls(self):
  self.reg(); self.spawn('writer','worktree'); wt=pathlib.Path(self.state()['agents']['session-a/writer']['worktree'])
  self.runcli('close','writer',ok=False,env=self.env|{'FAIL_CLOSE':'wtws'}); self.assertEqual(self.state()['agents']['session-a/writer']['state'],'closing')
  dirty=wt/'retry-dirty-fictional.txt'; dirty.write_text('retain on refusal'); n=len(self.calls())
  p=self.runcli('close','writer',ok=False); self.assertIn('retry-dirty-fictional.txt',p.stderr); self.assertEqual(len(self.calls()),n); self.assertTrue(dirty.exists())
 def test_close_refuses_ignored_paths_without_stopping(self):
  self.reg(); self.spawn('writer','worktree'); wt=pathlib.Path(self.state()['agents']['session-a/writer']['worktree']); (wt/'.gitignore').write_text('ignored-fictional.txt\n'); (wt/'ignored-fictional.txt').write_text('ignored'); n=len(self.calls())
  p=self.runcli('close','writer',ok=False); self.assertIn('ignored-fictional.txt',p.stderr); self.assertEqual(len(self.calls()),n)
 def test_close_refuses_unmerged_branch(self):
  self.reg(); self.spawn('writer','worktree'); wt=pathlib.Path(self.state()['agents']['session-a/writer']['worktree']); (wt/'change.txt').write_text('change')
  subprocess.run(['git','-C',str(wt),'add','change.txt'],check=True,env=self.env); subprocess.run(['git','-C',str(wt),'commit','-qm','unmerged fictional change'],check=True,env=self.env)
  n=len(self.calls()); p=self.runcli('close','writer',ok=False); self.assertIn('unmerged commits:',p.stderr); self.assertEqual(len(self.calls()),n)
 def test_discard_overrides_close_preflight(self):
  self.reg(); self.spawn('writer','worktree'); wt=pathlib.Path(self.state()['agents']['session-a/writer']['worktree']); (wt/'change.txt').write_text('unmerged change')
  subprocess.run(['git','-C',str(wt),'add','change.txt'],check=True,env=self.env); subprocess.run(['git','-C',str(wt),'commit','-qm','unmerged fictional change'],check=True,env=self.env)
  self.runcli('close','writer','--discard'); self.assertEqual(self.state()['agents']['session-a/writer']['state'],'closed')
  self.assertIn(['worktree','remove','--workspace','wtws'],self.calls())
  self.assertNotIn('--force',[arg for call in self.calls() for arg in call])
 def test_discard_removes_untracked_and_modified_worktrees_without_force(self):
  for kind in ('untracked','tracked-modified'):
   with self.subTest(kind=kind):
    self.reg('p1','session-a'); self.spawn('dirty-'+kind,'worktree'); wt=pathlib.Path(self.state()['agents']['session-a/dirty-'+kind]['worktree'])
    if kind=='untracked': (wt/'untracked-fictional.txt').write_text('unsaved')
    else: (wt/'seed.txt').write_text('modified fictional seed')
    self.runcli('close','dirty-'+kind,'--discard'); self.assertFalse(wt.exists()); self.assertNotIn('--force',[arg for call in self.calls() for arg in call])
 def test_close_only_created_and_discard_override(self):
  self.reg(); self.spawn('tabber','tab'); self.runcli('close','tabber','--keep-checkout'); c=self.calls(); self.assertIn(['agent','send-keys','tabber','ctrl+c'],c); self.assertIn(['pane','close','--pane','tabpane'],c); self.assertIn(['tab','close','--tab','newtab'],c)
 def test_python_version_guard(self):
  import sys
  sys.path.insert(0,str(ROOT/'plugin'))
  import orchlib
  old=orchlib.sys.version_info
  try:
   orchlib.sys.version_info=(3,10)
   with self.assertRaises(SystemExit): orchlib.require_runtime()
  finally: orchlib.sys.version_info=old; sys.path.remove(str(ROOT/'plugin'))
if __name__=='__main__': unittest.main()
