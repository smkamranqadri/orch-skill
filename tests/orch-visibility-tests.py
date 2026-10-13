"""Visibility features of orch-watch.py: marks, the board's evidence column and Needs-you block,
check, show and stats. Temporary run dirs and a fake Herdr only; fixtures under
tests/fixtures/visibility are copies of the real 2026-10-13 run (events.log, ledger.md, agents.txt)."""
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/orch/scripts/orch-watch.py'
FIX = ROOT / 'tests/fixtures/visibility'
spec = importlib.util.spec_from_file_location('watch', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

UTC = dt.timezone.utc


def at(stamp):
    return dt.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.d = self.root / 'run'
        self.d.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.live = {}
        fake = self.bin / 'herdr'
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args=sys.argv[1:]; d=Path(os.environ['VIS_TEST_DIR'])
with (d/'calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
live=json.loads((d/'live.json').read_text())
if args[:2]==['agent','list']: print(json.dumps({'result':{'agents':list(live.values())}}))
elif args[:2]==['agent','read']: print('› ')
elif args[:2]==['agent','prompt']: sys.exit(0)
''')
        fake.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith('HERDR_')}
        env.update(PATH=str(self.bin) + os.pathsep + os.environ['PATH'], VIS_TEST_DIR=str(self.root),
                   PYTHONDONTWRITEBYTECODE='1')
        self.envpatch = patch.dict(os.environ, env, clear=True)
        self.envpatch.start()
        self.addCleanup(self.envpatch.stop)
        self.write_live()
        patcher = patch.object(m.Watcher, 'refresh_usage', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_live(self):
        (self.root / 'live.json').write_text(json.dumps(self.live))

    def agent(self, name, state='idle', **extra):
        self.live[name] = dict(name=name, pane_id=name, agent_status=state, completion_seq=0, **extra)
        self.write_live()

    def log(self, *lines):
        with (self.d / 'events.log').open('a') as f:
            f.write(''.join(l + '\n' for l in lines))

    def log_text(self):
        p = self.d / 'events.log'
        return p.read_text() if p.exists() else ''

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env=dict(os.environ))


class MarkTests(Base):
    def test_mark_line_format(self):
        m.cmd_mark(str(self.d), ['lore-ids', 'verified', 'suite 399 pass', '--proof', '.orch/lore-ids/proof.log'])
        line = self.log_text().splitlines()[0]
        self.assertRegex(line, r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ lore-ids mark:verified a1 \| suite 399 pass \| proof \.orch/lore-ids/proof\.log$')
        m.cmd_mark(str(self.d), ['lore-ids', 'reported', 'agent says done'])
        self.assertTrue(self.log_text().splitlines()[1].endswith('| proof -'))
        events, bad = m.parse_log(str(self.d))
        self.assertEqual(bad, [])
        self.assertEqual([(e['tier'], e['attempt'], e['proof']) for e in events],
                         [('verified', 1, '.orch/lore-ids/proof.log'), ('reported', 1, '-')])

    def test_every_tier_is_accepted_and_unknown_refused(self):
        for tier in m.TIERS:
            m.cmd_mark(str(self.d), ['a', tier, 'x'])
        self.assertEqual(len(m.parse_log(str(self.d))[0]), len(m.TIERS))
        before = self.log_text()
        for bad in (['a', 'done', 'x'], ['a', 'verified', ''], ['a b', 'verified', 'x'], ['a', 'verified']):
            with self.assertRaises(ValueError):
                m.cmd_mark(str(self.d), bad)
        self.assertEqual(self.log_text(), before)

    def test_what_cannot_break_the_line(self):
        m.cmd_mark(str(self.d), ['a', 'asserted', 'cannot run | live probe\nneeds a device'])
        events, bad = m.parse_log(str(self.d))
        self.assertEqual(bad, [])
        self.assertEqual(events[0]['what'], 'cannot run / live probe needs a device')

    def test_attempts_count_sent_back_since_registered(self):
        d = str(self.d)
        m.cmd_add(d, ['a', '--orch', 'o1'])
        self.assertEqual(m.attempt_of(m.parse_log(d)[0], 'a'), 1)
        m.cmd_mark(d, ['a', 'sent-back', 'suite red'])
        m.cmd_mark(d, ['a', 'verified', 'suite green'])
        events = m.parse_log(d)[0]
        self.assertEqual([(e['tier'], e['attempt']) for e in events if e['kind'] == 'mark'],
                         [('sent-back', 2), ('verified', 2)])
        m.cmd_mark(d, ['a', 'sent-back', 'mutant survived'])
        self.assertEqual(m.attempt_of(m.parse_log(d)[0], 'a'), 3)
        # move keeps the count; remove then add starts a new life
        m.cmd_move(d, ['a', '--from', 'o1', '--orch', 'o2'])
        self.assertEqual(m.attempt_of(m.parse_log(d)[0], 'a'), 3)
        m.cmd_remove(d, ['a'])
        m.cmd_add(d, ['a', '--orch', 'o2'])
        self.assertEqual(m.attempt_of(m.parse_log(d)[0], 'a'), 1)

    def test_attempts_are_per_agent(self):
        d = str(self.d)
        m.cmd_add(d, ['a', 'b', '--orch', 'o'])
        m.cmd_mark(d, ['a', 'sent-back', 'x'])
        self.assertEqual(m.attempt_of(m.parse_log(d)[0], 'b'), 1)
        m.cmd_mark(d, ['wG:p6', 'handoff', 'ctx 150k'])  # unregistered owner pane names are allowed
        self.assertEqual(m.parse_log(d)[0][-1]['tier'], 'handoff')

    def test_registration_lines(self):
        d = str(self.d)
        m.cmd_orch(d, 'dflt')
        m.cmd_add(d, ['a', '--orch', 'o1'])
        m.cmd_add(d, ['b'])
        m.cmd_add(d, ['a', '--orch', 'o9'])  # already registered: no-op, no new line
        m.cmd_move(d, ['a', '--from', 'o1', '--orch', 'o2'])
        m.cmd_remove(d, ['a', 'ghost'])  # a name that was never registered gets no `removed`
        got = [(e['agent'], e['kind'], e.get('owner')) for e in m.parse_log(d)[0]]
        self.assertEqual(got, [('a', 'registered', 'o1'), ('b', 'registered', 'dflt'),
                               ('a', 'moved', 'o2'), ('a', 'removed', None)])
        with self.assertRaises(ValueError):
            m.cmd_move(d, ['b', '--from', 'wrong', '--orch', 'o3'])
        self.assertEqual(len(m.parse_log(d)[0]), 4)  # a refused move writes nothing

    def test_cli_mark(self):
        r = self.run_cli('mark', str(self.d), 'a', 'verified', 'ok', '--proof', 'p.log')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.run_cli('mark', str(self.d), 'a', 'bogus', 'x').returncode, 2)
        self.assertEqual(self.run_cli('mark', str(self.d), 'a', 'verified', 'x', '--proof').returncode, 2)
        self.assertEqual(len(m.parse_log(str(self.d))[0]), 1)


class ParserTests(Base):
    def test_real_log_grammar(self):
        (self.d / 'events.log').write_text((FIX / 'events.log').read_text())
        events, bad = m.parse_log(str(self.d))
        total = len((FIX / 'events.log').read_text().splitlines())
        self.assertEqual(total, 193)
        self.assertEqual(len(events) + len(bad), total)
        # Measured on the real log: four hand-written lines with a date and no time zone, and three
        # ISO-stamped free-form "closed"/"merged" lines.
        self.assertEqual([n for n, _ in bad], [103, 107, 182, 185, 188, 191, 192])
        kinds = {}
        for e in events:
            kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
        self.assertEqual(sorted(kinds), ['state', 'watcher', 'woken'])
        woken = [e for e in events if e['kind'] == 'woken']
        self.assertIn(None, {e['owner'] for e in woken})  # old shape: no owner
        self.assertIn('w3:pZ', {e['owner'] for e in woken})  # owner-tagged shape
        self.assertTrue(any(e['agents'] == ['orchfix'] for e in woken))

    def test_woken_shapes(self):
        for tail, owner in (('woken | lore', None), ('woken orch=wG:p5 | a, b', 'wG:p5'),
                            ('woken (file) orch=w3:pZ | a', 'w3:pZ')):
            e = m.parse_event(f'2026-10-13T10:00:00Z orchestrator {tail}')
            self.assertEqual((e['kind'], e['owner']), ('woken', owner))
        self.assertIsNone(m.parse_event('2026-10-13 10:00 a done; hand written'))
        self.assertIsNone(m.parse_event('2026-10-13T10:00:00Z a mark:bogus a1 | x | proof -'))

    def test_state_title_may_contain_bars(self):
        e = m.parse_event('2026-10-09T14:27:38Z orchfix blocked | [ . ] Action Required | Run orch follow-ups | orch-fixes | ctx -')
        self.assertEqual((e['state'], e['ctx']), ('blocked', '-'))

    def test_marks_do_not_move_since(self):
        d = str(self.d)
        m.cmd_add(d, ['a', '--orch', 'o'])
        self.agent('a', 'done')
        self.log('2026-10-13T10:00:00Z a done | task | ctx -')
        m.cmd_mark(d, ['a', 'verified', 'suite pass'])
        out = subprocess.run([sys.executable, str(SCRIPT), 'board', d], capture_output=True, text=True,
                             env=dict(os.environ)).stdout
        row = [l for l in out.splitlines() if l.startswith('a ')][0]
        self.assertIn(m.local('2026-10-13T10:00:00Z'), row)


if __name__ == '__main__':
    unittest.main(verbosity=2)
