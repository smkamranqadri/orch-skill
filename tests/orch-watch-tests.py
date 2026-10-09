"""Temporary run directories and fake Herdr only; no usage collector or real panes."""
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
if args[:2]==['agent','list']: print(json.dumps({'result':{'agents':list(live.values())}}))
elif args[:2]==['agent','read']:
    print('› '+('typed question' if live.get(args[2],{}).get('typing') else ''))
elif args[:2]==['agent','prompt']:
    sys.exit(1 if live.get(args[2],{}).get('reject') else 0)
''')
        fake.chmod(0o755)
        env = {k:v for k,v in os.environ.items() if not k.startswith('HERDR_')}
        env.update(PATH=str(self.d)+os.pathsep+os.environ['PATH'], WATCH_TEST_DIR=str(self.d))
        self.env = patch.dict(os.environ, env, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)
        self.write_live()
        m.cmd_orch(str(self.d), 'old')
        self.usage = patch.object(m.Watcher, 'refresh_usage', return_value=False)
        self.usage.start(); self.addCleanup(self.usage.stop)

    def write_live(self):
        (self.d/'live.json').write_text(json.dumps(self.live))

    def agent(self, name, state='idle', **extra):
        self.live[name] = dict(name=name, pane_id=name, agent_status=state,
                               completion_seq=0, **extra)
        self.write_live()

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
        w.poll(); self.assertEqual(len(w.recent),5)
        self.agent('old')
        for i in range(8): self.agent(f'x{i}','done')
        w.poll(); self.assertEqual(len(w.recent),5)
        self.assertIn('orchestrator woken', (self.d/'events.log').read_text())

    def test_redraw(self):
        w=m.Watcher(str(self.d))
        with patch.object(m.Watcher,'board',side_effect=['same','same','changed','changed']), patch.object(m.sys,'stdout',new_callable=io.StringIO) as out:
            for _ in range(4): w.draw()
            self.assertEqual(out.getvalue().count('\033[H\033[2J'),2)
            self.assertEqual(out.getvalue(),'\033[H\033[2Jsame\n\033[H\033[2Jchanged\n')

    def test_terminal_restore(self):
        class Terminal(io.StringIO):
            def isatty(self): return True
        term=Terminal()
        old=signal.getsignal(signal.SIGTERM)
        try:
            with patch.object(m.sys,'stdout',term), patch.object(m.time,'sleep',side_effect=SystemExit(0)):
                with self.assertRaises(SystemExit): m.cmd_watch(str(self.d), [])
            self.assertTrue(term.getvalue().startswith('\033[?1049h\033[?25l'))
            self.assertTrue(term.getvalue().endswith('\033[?25h\033[?1049l'))
        finally: signal.signal(signal.SIGTERM,old)

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
