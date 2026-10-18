"""Temporary run directories and fake Herdr only; no usage collector or real panes.
Sleeps use a fake clock, so the event wake and the hourly call count run in milliseconds."""
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/orch/scripts/orch-watch.py'
spec = importlib.util.spec_from_file_location('watch', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.live = {}
        self.calls = self.d / 'calls.jsonl'
        fake = self.d / 'herdr'
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]; d=Path(os.environ['WATCH_TEST_DIR'])
with (d/'calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
live=json.loads((d/'live.json').read_text())
if args[:2]==['agent','list'] and (d/'down').exists(): sys.exit(1)
if args[:2]==['agent','list']: print(json.dumps({'result':{'agents':list(live.values())}}))
elif args[:2]==['agent','read']:
    print('no input box here' if live.get(args[2],{}).get('nobox') else '› '+('typed question' if live.get(args[2],{}).get('typing') else ''))
elif args[:2]==['agent','prompt']:
    sys.exit(1 if live.get(args[2],{}).get('reject') else 0)
''')
        fake.chmod(0o755)
        env = {k:v for k,v in os.environ.items() if not k.startswith('HERDR_')}
        env.update(PATH=str(self.d)+os.pathsep+os.environ['PATH'], WATCH_TEST_DIR=str(self.d),
                   XDG_CACHE_HOME=str(self.d/'cache'), ORCH_USAGE_CACHE_DIR=str(self.d/'cache'/'orch'))
        self.env = patch.dict(os.environ, env, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        self.write_live()
        m.cmd_orch(str(self.d), 'old')
        self.signal = Path(m.signal_path())
        self.signal.parent.mkdir(parents=True)

    def write_live(self):
        (self.d/'live.json').write_text(json.dumps(self.live))

    def agent(self, name, state='idle', **extra):
        self.live[name] = dict(name=name, pane_id=name, agent_status=state,
                               completion_seq=0, **extra)
        self.write_live()

    def lists(self):
        return [x for x in self.read_calls() if x[:2]==['agent','list']]

    def emit(self, pane, status, event='pane.agent_status_changed'):
        with self.signal.open('a') as f:
            f.write(json.dumps({'ts':1,'event':event,'pane':pane,'status':status})+'\n')

    def clock(self, at=None):
        """A fake clock for Watcher.sleep and .mono; `at` maps a second to a callback run when the
        clock first reaches it (an event arriving, a turn finishing)."""
        class Clock:
            t=0.0
            def mono(c): return c.t
            def sleep(c, secs):
                c.t+=secs
                for when in sorted(k for k in (at or {}) if k<=c.t): (at or {}).pop(when)()
        return Clock()

    def prompts(self):
        return [x for x in self.read_calls() if x[:2]==['agent','prompt']]

    def read_calls(self):
        return [json.loads(l) for l in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def watcher(self):
        w=m.Watcher(str(self.d)); w.poll(); return w

    def test_per_owner(self):
        m.cmd_add(str(self.d), ['a','b','--orch','old'])
        m.cmd_add(str(self.d), ['c','--orch','other'])
        for n in ['a','b','c']: self.agent(n,'working')
        self.agent('old','working'); self.agent('other')
        w=self.watcher()
        for n in ['a','b','c']: self.agent(n,'done')
        w.poll()
        self.assertEqual([p[2] for p in self.prompts()], ['other'])
        self.assertIn('c finished', self.prompts()[0][3])
        self.assertNotIn('a finished', self.prompts()[0][3])
        self.assertEqual([e[1] for e in w.pending], ['a','b'])
        # A typing owner stays held; the other still gets a second short-turn completion.
        self.agent('old',typing=True); self.agent('c','idle')
        self.live['c']['completion_seq']=1; self.write_live()
        w.next_try.clear(); w.poll()
        self.assertEqual([p[2] for p in self.prompts()], ['other','other'])
        self.agent('old'); w.next_try.clear(); w.poll()
        self.assertEqual(self.prompts()[-1][2], 'old')
        self.assertIn('a finished',self.prompts()[-1][3]); self.assertIn('b finished',self.prompts()[-1][3])
        self.assertFalse(w.pending)

    def test_fallback(self):
        m.cmd_add(str(self.d), ['legacy'])
        self.assertEqual((self.d/'agents.txt').read_text(), 'legacy\n')
        self.agent('legacy','working'); self.agent('old')
        w=self.watcher(); self.agent('legacy','done'); w.poll()
        self.assertEqual([p[2] for p in self.prompts()], ['old'])
        self.assertEqual(w.owners['legacy'], 'old')
        self.assertIn('old',w.board())

    def test_move(self):
        m.cmd_add(str(self.d), ['a','--orch','old']); m.cmd_add(str(self.d), ['b','--orch','other'])
        self.agent('a','working'); self.agent('old','working'); self.agent('new'); self.agent('other')
        w=self.watcher(); self.agent('a','done'); w.poll()
        before=(self.d/'agents.txt').read_bytes()
        with self.assertRaises(ValueError): m.cmd_move(str(self.d), ['a','b','--from','old','--orch','new'])
        self.assertEqual((self.d/'agents.txt').read_bytes(),before)
        m.cmd_move(str(self.d), ['a','--from','old','--orch','new']); w.poll()
        self.assertEqual([p[2] for p in self.prompts()],['new'])
        self.assertEqual(m.registrations(str(self.d)),{'a':'new','b':'other'})
        self.assertFalse(w.pending)
        m.cmd_add(str(self.d), ['a','--orch','other'])
        self.assertEqual(m.registrations(str(self.d))['a'],'new')
        m.cmd_remove(str(self.d), ['a'])
        self.assertEqual(m.registrations(str(self.d)),{'b':'other'})

    def test_recent_five(self):
        (self.d/'events.log').write_text(''.join(f'2026-10-09T12:00:0{i}Z a{i} done | task\n' for i in range(8)))
        w=m.Watcher(str(self.d)); self.assertEqual(len(w.recent),5)
        self.assertIn('a3',w.recent[0]); self.assertIn('a7',w.recent[-1])
        m.cmd_add(str(self.d), [f'x{i}' for i in range(8)])
        for i in range(8): self.agent(f'x{i}','working')
        w.poll(); self.agent('old')
        for i in range(8): self.agent(f'x{i}','done')
        w.poll()
        self.assertIn('orchestrator woken', (self.d/'events.log').read_text())
        self.assertEqual(len(m.Watcher(str(self.d)).recent),5)   # the board rebuilds Recent from the log

    def run_watch(self, clock, until):
        """cmd_watch under the fake clock; stops when the clock passes `until` seconds."""
        real=clock.sleep
        def stop(secs):
            real(secs)
            if clock.t>=until: raise SystemExit(0)
        old=signal.getsignal(signal.SIGTERM)
        out=io.StringIO()
        try:
            with patch.object(m.Watcher,'sleep',staticmethod(stop)), patch.object(m.Watcher,'mono',staticmethod(clock.mono)), \
                 patch.object(m.sys,'stdout',out):
                with self.assertRaises(SystemExit): m.cmd_watch(str(self.d), [])
        finally: signal.signal(signal.SIGTERM,old)
        return out.getvalue()

    def test_headless(self):
        out=self.run_watch(self.clock(), 1)
        lines=out.splitlines()
        self.assertEqual(len(lines),1)
        self.assertRegex(lines[0], r'^orch watcher pid \d+ · ')
        self.assertNotIn('\033',out)
        self.assertTrue((self.d/'watcher.pid').exists())

    def test_an_event_during_a_poll_wakes_the_next_wait(self):
        """cmd_watch takes its stamp before the poll: an event that lands mid-poll must not wait 60 s."""
        c=self.clock(); times=[]; real=m.Watcher.poll
        def poll(w):
            times.append(c.t)
            if len(times)==1: self.emit('a','working')
            return real(w)
        with patch.object(m.Watcher,'poll',poll): self.run_watch(c, 5)
        self.assertEqual(times,[0.0,0.5])

    def test_short_turn_is_caught_by_completion_seq(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','idle'); self.agent('old')
        w=self.watcher()
        self.assertEqual(self.prompts(),[])
        self.live['a']['completion_seq']=1; self.write_live()   # a whole turn between two reads
        w.poll()
        self.assertRegex((self.d/'events.log').read_text(), r'(?m)^\S+ a done \| ')
        self.assertEqual([p[2] for p in self.prompts()],['old'])
        self.assertIn('a finished',self.prompts()[0][3])

    def test_safety_poll_catches_a_short_turn_with_no_event(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','idle'); self.agent('old')
        w=self.watcher()
        def turn(): self.live['a']['completion_seq']=1; self.write_live()
        c=self.clock({10:turn}); w.sleep=c.sleep; w.mono=c.mono
        before=w.stamp()
        self.assertFalse(w.wait(before))
        self.assertEqual(c.t,m.SAFETY_POLL)
        w.poll()
        self.assertRegex((self.d/'events.log').read_text(), r'(?m)^\S+ a done \| ')
        self.assertEqual(len(self.prompts()),1)

    def test_signal_wakes_the_wait(self):
        w=m.Watcher(str(self.d))
        c=self.clock({3:lambda: self.emit('a','idle')}); w.sleep=c.sleep; w.mono=c.mono
        self.assertTrue(w.wait(w.stamp()))
        self.assertEqual(c.t,3.0)

    def test_registration_change_wakes_the_wait(self):
        w=m.Watcher(str(self.d))
        c=self.clock({3:lambda: m.cmd_add(str(self.d),['a'])}); w.sleep=c.sleep; w.mono=c.mono
        self.assertTrue(w.wait(w.stamp()))
        self.assertEqual(c.t,3.0)

    def test_an_event_during_the_poll_is_not_lost(self):
        w=m.Watcher(str(self.d))
        before=w.stamp()
        self.emit('a','working')   # lands after the stamp, before the wait starts
        c=self.clock(); w.sleep=c.sleep; w.mono=c.mono
        self.assertTrue(w.wait(before))
        self.assertEqual(c.t,0.0)

    def test_signal_lines_are_read_once_and_history_is_skipped(self):
        self.emit('old-pane','done')
        w=m.Watcher(str(self.d))
        w.read_signal(); self.assertEqual(w.signalled,{})
        self.emit('p1','idle'); self.emit('p2',None)
        with self.signal.open('a') as f: f.write('not json\n{"pane": 3}\n{"pane":"p3","status":"working"')
        w.read_signal()
        self.assertEqual(w.signalled,{'p1':'idle','p2':None})
        w.read_signal(); self.assertEqual(w.signalled,{})
        with self.signal.open('a') as f: f.write('}\n')   # the half line completes on the next read
        w.read_signal(); self.assertEqual(w.signalled,{'p3':'working'})

    def test_signal_file_is_truncated_past_one_megabyte(self):
        w=m.Watcher(str(self.d))
        line=json.dumps({'ts':1,'event':'pane.closed','pane':'p','status':None})+'\n'
        self.signal.write_text(line*(m.SIGNAL_MAX//len(line)+10))
        self.assertGreater(self.signal.stat().st_size,m.SIGNAL_MAX)
        w.read_signal()
        self.assertEqual(self.signal.stat().st_size,0)
        self.assertEqual(w.signalled,{'p':None})
        self.emit('q','idle'); w.read_signal()
        self.assertEqual(w.signalled,{'q':'idle'})
        # Exactly at the limit is left alone.
        self.signal.write_text('x'*m.SIGNAL_MAX); w.signal_pos=m.SIGNAL_MAX; w.read_signal()
        self.assertEqual(self.signal.stat().st_size,m.SIGNAL_MAX)

    def test_owner_idle_event_skips_the_retry_wait(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        w=self.watcher(); self.agent('a','done'); w.poll()
        self.assertEqual(self.prompts(),[]); self.assertTrue(w.pending)
        self.agent('old'); w.poll()                       # no event: the 30 s retry still holds it
        self.assertEqual(self.prompts(),[])
        w.signalled={'old':'working'}; w.poll()           # the owner started a turn: still waiting
        self.assertEqual(self.prompts(),[])
        w.signalled={'old':'idle'}; w.poll()              # the owner went idle: try now
        self.assertEqual([p[2] for p in self.prompts()],['old'])
        self.assertFalse(w.pending)

    def test_wait_ends_when_a_held_wake_is_due(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        c=self.clock(); w=m.Watcher(str(self.d)); w.sleep=c.sleep; w.mono=c.mono
        w.poll(); self.agent('a','done'); w.poll()
        self.assertTrue(w.pending)
        self.assertFalse(w.wait(w.stamp()))
        self.assertAlmostEqual(c.t,m.RETRY,delta=1.5)
        w.pending=[]; c.t=0
        self.assertFalse(w.wait(w.stamp())); self.assertEqual(c.t,m.SAFETY_POLL)

    def test_typed_text_reads_the_input_box(self):
        def reading(out, code=0):
            return patch.object(m,'herdr',return_value=(code,out))
        with reading('output\n❯ \n'): self.assertEqual(m.typed_text('t'),'')
        with reading('❯ fix the bug\n'): self.assertEqual(m.typed_text('t'),'fix the bug')
        with reading('› \x1b[2mTry "refactor this"\x1b[0m\n'): self.assertEqual(m.typed_text('t'),'')   # dim suggestion
        with reading('› Ask Codex to anything\n'): self.assertEqual(m.typed_text('t'),'')            # known placeholder
        with reading('› typed \x1b[2mhint\x1b[0m\n'): self.assertEqual(m.typed_text('t'),'typed')
        with reading('no box here\n'): self.assertIsNone(m.typed_text('t'))
        with reading('', code=1): self.assertIsNone(m.typed_text('t'))

    def test_typing_owner_is_never_prompted(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        w=self.watcher(); self.agent('a','done')
        for _ in range(3): w.next_try.clear(); w.poll()
        self.assertEqual(self.prompts(),[])
        self.assertEqual([e[1] for e in w.pending],['a'])
        self.agent('old'); w.next_try.clear(); w.poll()
        self.assertEqual([p[2] for p in self.prompts()],['old'])

    def test_unreadable_input_box_holds_a_focused_owner(self):
        """typed_text is None when no input box is seen: the user may be typing into something the
        reader cannot parse, so a focused owner is held and an unfocused one is prompted."""
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',nobox=True,focused=True)
        w=self.watcher(); self.agent('a','done'); self.agent('old',nobox=True,focused=True)
        w.poll()
        self.assertEqual(self.prompts(),[])
        self.assertEqual([e[1] for e in w.pending],['a'])
        self.assertIn('typed input or is focused',w.owner_note)
        self.agent('old',nobox=True,focused=False); w.next_try.clear(); w.poll()
        self.assertEqual([p[2] for p in self.prompts()],['old'])
        self.assertFalse(w.pending)

    def test_herdr_down_does_not_busy_poll(self):
        """A held wake is due for another try, but Herdr is unreachable so none is made: the wait
        falls back to the 60 s safety poll instead of 1 s."""
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        def finish(): self.agent('a','done')
        def down(): (self.d/'down').write_text('')
        c=self.clock({10:finish,61:down})
        self.run_watch(c, 300)
        # start, 60 s (the finish, held), 90 s (the retry, Herdr down), then 150, 210, 270
        self.assertEqual(len(self.lists()),6)

    def test_hold_notice_follows_the_monotonic_clock(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        c=self.clock(); w=m.Watcher(str(self.d)); w.sleep=c.sleep; w.mono=c.mono
        w.poll(); self.agent('a','done')
        shown=[]
        with patch.object(w,'notify',lambda t,b: shown.append(t) if t.startswith('orchestrator') else None), patch.object(m.time,'time',lambda: 1e9 + c.t) as _:
            w.poll()                                  # held; wall clock and monotonic clock agree
            self.assertEqual(shown,[])
            with patch.object(m.time,'time',lambda: 1e9 + c.t + 7200):
                c.t+=m.RETRY; w.poll()                # the wall clock jumps forward 2 h: no notice
            self.assertEqual(shown,[])
            with patch.object(m.time,'time',lambda: 1e9 + c.t - 7200):
                c.t+=m.HOLD_NOTICE; w.poll()          # the wall clock jumps back 2 h: the notice still comes
            self.assertEqual(shown,['orchestrator: events waiting'])

    def test_the_real_plugin_hook_line_is_what_the_watcher_parses(self):
        """Contract: run plugin/event-hook.py as Herdr would (HERDR_PLUGIN_EVENT[_JSON], a temp
        XDG_CACHE_HOME), read its line with the watcher, and check the pane in it is the
        `agent list` pane_id by letting it skip the retry wait of a held wake."""
        hook=ROOT/'skills/orch/plugin/event-hook.py'
        def fire(event, data):
            env=dict(os.environ, HERDR_PLUGIN_EVENT=event,
                     HERDR_PLUGIN_EVENT_JSON=json.dumps({'event':event.replace('.','_',1),'data':data}))
            r=subprocess.run([sys.executable,'-I',str(hook)],env=env,capture_output=True,text=True)
            self.assertEqual((r.returncode,r.stderr),(0,''))
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',typing=True)
        self.live['old']['pane_id']='w9:p2'
        self.write_live()
        w=self.watcher(); self.agent('a','done'); self.live['old']['pane_id']='w9:p2'; self.write_live()
        w.poll()
        self.assertTrue(w.pending); self.assertEqual(self.prompts(),[])
        pane=m.agent_list()['old']['pane_id']
        self.assertEqual(pane,'w9:p2')
        self.agent('old'); self.live['old']['pane_id']=pane; self.write_live()
        fire('pane.agent_status_changed',{'pane_id':pane,'agent_status':'idle'})
        w.read_signal()
        self.assertEqual(w.signalled,{pane:'idle'})
        w.poll()                                           # no next_try.clear(): the event alone skips the wait
        self.assertEqual([p[2] for p in self.prompts()],['old'])
        fire('pane.closed',{'pane_id':pane})
        w.read_signal()
        self.assertEqual(w.signalled,{pane:None})
        self.assertEqual(len(self.signal.read_text().splitlines()),2)

    def test_list_calls_per_hour(self):
        """One agent working, three events in the hour: the loop reads Herdr on start, on each event
        and on each 60 s timeout. Before this change the same hour cost 3600/4 = 900 reads."""
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old')
        def finish(): self.agent('a','done'); self.emit('a','done')
        def restart(): self.agent('a','working'); self.emit('a','working')
        c=self.clock({100:finish,1000:restart,2000:finish})
        self.run_watch(c, 3600)
        n=len(self.lists())
        # start, 57 timeouts of 60 s (3600 s minus the three event wakes), and the three events
        self.assertEqual(n,61)
        self.assertEqual([p[2] for p in self.prompts()],['old','old'])   # both finishes woke the owner
        self.assertLess(n,900/10)
        print(f'herdr agent list calls in one fake hour: {n} (was 900 at a 4 s poll)')

    def test_an_event_is_read_within_the_settle_pause(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old')
        def finish(): self.agent('a','done'); self.emit('a','done')
        c=self.clock({100:finish})
        self.run_watch(c, 105)
        self.assertEqual(len(self.prompts()),1)
        self.assertEqual(len(self.lists()),3)    # start, the 60 s read, then the event at 100 (read at 100.5)
        self.assertIn(' a done | ',(self.d/'events.log').read_text())

    def test_file_wake_owner(self):
        m.cmd_add(str(self.d), ['a','--orch','old'])
        self.agent('a','working'); self.agent('old',reject=True)
        w=self.watcher(); self.agent('a','done'); w.poll()
        self.assertIn('orch=old', (self.d/'wake.md').read_text())
        self.assertFalse(w.pending)

    def test_cli_registration(self):
        def run(*args):
            return subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,text=True)
        self.assertEqual(run('add',str(self.d),'a','--orch','old').returncode,0)
        self.assertEqual(run('move',str(self.d),'a','--from','other','--orch','new').returncode,2)
        self.assertEqual(run('move',str(self.d),'a','--from','old','--orch','new').returncode,0)
        self.assertEqual(m.registrations(str(self.d)),{'a':'new'})

if __name__=='__main__': unittest.main(verbosity=2)
