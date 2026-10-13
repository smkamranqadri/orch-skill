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


class BoardTests(Base):
    T0 = '2026-10-13T10:00:00Z'

    def setup_agent(self, name='a', owner='o1', state='done', when=None):
        m.cmd_add(str(self.d), [name, '--orch', owner])
        self.agent(name, state)
        self.agent(owner, 'idle')
        self.log(f'{when or self.T0} {name} {state} | task | ctx 10k/200k')

    def board(self, minutes=0, seconds=0, **kw):
        w = m.Watcher(str(self.d))
        w.owners = m.registrations(str(self.d))
        live = m.agent_list() or {}
        for n in w.owners:
            w.prev[n] = live[n]['agent_status'] if n in live else 'gone'
            w.since[n] = self.T0
            w.info[n] = ('task', '')
        for k, v in kw.items():
            setattr(w, k, v)
        return w.board(at(self.T0) + dt.timedelta(minutes=minutes, seconds=seconds))

    def needs(self, text):
        lines = text.splitlines()
        if not any(l.startswith('NEEDS YOU') for l in lines):
            return []
        i = [l.startswith('NEEDS YOU') for l in lines].index(True)
        out = []
        for l in lines[i + 1:]:
            if not l.startswith('  '):
                break
            out.append(l.strip())
        return out

    def row(self, text, name='a'):
        return [l for l in text.splitlines() if l.startswith(name + ' ')][0]

    def test_evid_sequence(self):
        self.setup_agent()
        self.assertNotRegex(self.row(self.board()), '[◆◇↩⇢]|asserted')  # blank before any mark
        m.cmd_mark(str(self.d), ['a', 'reported', 'says done'])
        self.assertIn('◇ reported', self.row(self.board()))
        m.cmd_mark(str(self.d), ['a', 'sent-back', 'suite red'])
        self.assertIn('↩ a2', self.row(self.board()))
        m.cmd_mark(str(self.d), ['a', 'verified', 'suite pass'])
        self.assertIn('◆ verified', self.row(self.board()))
        m.cmd_mark(str(self.d), ['a', 'asserted', 'no device'])
        self.assertIn('! asserted', self.row(self.board()))
        m.cmd_mark(str(self.d), ['a', 'merged', 'abc123'])
        self.assertIn('⇢ merged', self.row(self.board()))

    def test_evid_starts_over_after_reregistration(self):
        self.setup_agent()
        m.cmd_mark(str(self.d), ['a', 'verified', 'x'])
        m.cmd_remove(str(self.d), ['a'])
        m.cmd_add(str(self.d), ['a', '--orch', 'o1'])
        self.assertNotIn('◆', self.row(self.board()))

    def test_finished_boundary(self):
        self.setup_agent()
        self.assertEqual(self.needs(self.board(minutes=9, seconds=59)), [])
        self.assertEqual(self.needs(self.board(minutes=9)), [])
        got = self.needs(self.board(minutes=10))
        self.assertEqual(len(got), 1)
        self.assertIn('a finished 10m ago, no verdict marked', got[0])
        self.assertIn('a finished 11m ago', self.needs(self.board(minutes=11))[0])
        m.cmd_mark(str(self.d), ['a', 'reported', 'x'])
        self.assertNotIn('finished', ' '.join(self.needs(self.board(minutes=11))))

    def test_mark_before_finish_does_not_count(self):
        self.setup_agent()
        self.log('2026-10-13T10:20:00Z a working | task | ctx -',
                 '2026-10-13T10:21:00Z a mark:verified a1 | old | proof -',
                 '2026-10-13T10:25:00Z a done | task | ctx -')
        w = self.needs(self.board(minutes=40))
        self.assertEqual(len(w), 1)
        self.assertIn('a finished 15m ago, no verdict marked', w[0])

    def test_reported_boundary(self):
        self.setup_agent(state='idle')
        self.log('2026-10-13T10:01:00Z a mark:reported a1 | says done | proof -')
        # idle after idle is no finish; only the report is listed
        self.assertEqual(self.needs(self.board(minutes=10, seconds=59)), [])
        got = self.needs(self.board(minutes=11))
        self.assertEqual(len(got), 1)
        self.assertIn('a reported 10m ago, not verified', got[0])

    def test_unclosed_boundary_and_open_closed(self):
        self.setup_agent(state='idle')
        self.log('2026-10-13T10:00:00Z a mark:verified a1 | pass | proof p')
        self.assertEqual(self.needs(self.board(minutes=29, seconds=59)), [])
        got = self.needs(self.board(minutes=30))
        self.assertIn('a verified 30m ago, not closed', got[0])
        self.log('2026-10-13T10:31:00Z a mark:merged a1 | abc | proof -')
        self.assertIn('a merged', self.needs(self.board(minutes=61))[0])
        self.log('2026-10-13T10:32:00Z a mark:open a1 | next cycle: round 2 | proof -')
        self.assertEqual(self.needs(self.board(minutes=120)), [])
        self.log('2026-10-13T10:33:00Z a mark:closed a1 | gone | proof -')
        self.assertEqual(self.needs(self.board(minutes=120)), [])

    def test_blocked_and_order_and_limit(self):
        for i in range(7):
            self.setup_agent(f'a{i}', when=f'2026-10-13T10:{10 + i}:00Z')
        self.agent('a3', 'blocked')
        out = self.board(minutes=30)
        lines = out.splitlines()
        self.assertTrue(lines[[l.startswith('NEEDS YOU') for l in lines].index(True)].endswith('(7)'))
        got = self.needs(out)
        self.assertEqual(len(got), 6)
        self.assertEqual(got[-1], '+2 more')
        self.assertIn('a3 is blocked and needs you', got[0])  # waiting since 10:00, the oldest
        self.assertIn('a0 finished', got[1])
        self.assertIn('a1 finished', got[2])
        self.assertFalse(any('a6 finished' in l for l in got))  # cut by the limit

    def test_block_omitted_when_empty(self):
        self.setup_agent(state='working')
        out = self.board(minutes=30)
        self.assertNotIn('NEEDS YOU', out)

    def test_wakes_waiting_and_usage(self):
        self.setup_agent(state='working')
        (self.d / 'ledger.md').write_text('Waiting on user: (0) full permissions asked 10-09\n')
        w = m.Watcher(str(self.d))
        w.owners = m.registrations(str(self.d))
        w.prev = {'a': 'working'}; w.since = {'a': self.T0}; w.info = {'a': ('t', '')}
        w.pending = [(self.T0, 'a', 'done')]
        w.held_since = {'o1': at(self.T0).timestamp()}
        w.usage = 'claude 25%/94% ASK · codex 10%/10% · cmd 0%/86% ASK'
        got = self.needs(w.board(at(self.T0) + dt.timedelta(minutes=1)))
        self.assertEqual(got[0].split(' ', 1)[1], '1 wake(s) held for o1')
        self.assertEqual(got[1], 'waiting on user: (0) full permissions asked 10-09')
        self.assertEqual(got[2], 'usage ASK: claude, cmd')
        (self.d / 'ledger.md').write_text('Waiting on user: none.\n')
        w.usage = ''; w.held_since = {}
        self.assertEqual(self.needs(w.board(at(self.T0))), [])

    def test_restart_keeps_the_clock(self):
        self.setup_agent()
        a = self.needs(self.board(minutes=15))
        b = self.needs(self.board(minutes=15))  # a new Watcher over the same log
        self.assertEqual(a, b)
        self.assertEqual(len(a), 1)

    def test_recent_shows_marks_in_words(self):
        self.setup_agent()
        m.cmd_mark(str(self.d), ['a', 'verified', 'suite 399 pass'])
        m.cmd_mark(str(self.d), ['a', 'sent-back', 'mutant survived'])
        w = m.Watcher(str(self.d))
        self.assertTrue(any(r.endswith('a verified: suite 399 pass') for r in w.recent))
        self.assertTrue(any(r.endswith('a sent back: mutant survived') for r in w.recent))
        m.cmd_mark(str(self.d), ['a', 'merged', 'abc'])
        w.owners = m.registrations(str(self.d))
        w.poll()
        self.assertTrue(any(r.endswith('a merged: abc') for r in w.recent))
        self.assertEqual(len(w.recent), 5)

    def test_cli_board_accepts_now(self):
        self.setup_agent()
        r = self.run_cli('board', str(self.d), '--now', '2026-10-13T10:11:00Z')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('a finished 11m ago', r.stdout)
        self.assertEqual(self.run_cli('board', str(self.d), '--now', 'tomorrow').returncode, 2)


class CheckTests(Base):
    def make_run(self, rows=(), nexts=('o1',), watcher=None, pad=0, agents=(), events=()):
        lines = ['# Orchestrator ledger: test', 'Updated: now']
        lines += [f'Next action ({o}): do the next thing' if o else '' for o in nexts]
        lines += ['Waiting on user: none', '', '## Pane agents',
                  '| name | kind/model | pane | worktree / branch | brief | handoff | status | last event |',
                  '|---|---|---|---|---|---|---|---|']
        for name, status in rows:
            lines.append(f'| {name} | claude/sonnet | - | wt / br | .orch/{name}/brief.md | .orch/{name}/handoff.md | {status} | 10-13 10:00 x |')
        lines += ['', '## Sub-agents and background jobs', '| name | type | status |', '|---|---|---|', '',
                  '## Watcher', watcher if watcher is not None else
                  f'pane wX:p1, pid {os.getpid()}, agents: {" ".join(n for n, _ in agents) or "none"} (.orch/agents.txt), log: .orch/events.log']
        lines += [f'- filler {i}' for i in range(pad)]
        (self.d / 'ledger.md').write_text('\n'.join(lines) + '\n')
        (self.d / 'agents.txt').write_text(''.join(f'{n} orch={o}\n' for n, o in agents))
        if events:
            self.log(*events)
        (self.d / 'orchestrator').write_text('o1\n')

    def check(self, *args):
        out = io.StringIO()
        err = io.StringIO()
        with patch.object(m.sys, 'stdout', out), patch.object(m.sys, 'stderr', err):
            code = m.cmd_check(str(self.d), list(args))
        return code, out.getvalue().splitlines(), err.getvalue()

    def rules(self, lines):
        return [re.search(r'\[([a-z-]+)\]', l).group(1) for l in lines]

    def test_clean_run(self):
        self.make_run(rows=[('a', 'working'), ('b', 'closed: merged abc')], agents=[('a', 'o1')])
        self.assertEqual(self.check('--offline'), (0, ['check: clean'], ''))

    def test_todays_run_acceptance(self):
        for n in ('events.log', 'ledger.md', 'agents.txt'):
            (self.d / n).write_text((FIX / n).read_text())
        with patch.object(m, 'pid_alive', return_value=False):
            code, lines, _ = self.check('--offline')
        self.assertEqual(code, 1)
        self.assertEqual(self.rules(lines), ['ledger-length', 'not-closed', 'not-closed', 'not-closed', 'watcher', 'watcher', 'log'])
        self.assertIn('ledger has 79 lines, the limit is 60', lines[0])
        self.assertEqual([l.split(': ')[0] for l in lines[1:4]], ['w3:pZ'] * 3)
        self.assertEqual(sorted(l.split('] ')[1].split(':')[0] for l in lines[1:4]), ['ctx-trims', 'lore-ids', 'tartib-search'])
        self.assertIn('watcher pid 59865 is not alive', lines[4])
        self.assertIn("lists agents none but agents.txt holds ['ctx-trims', 'lore-ids', 'tartib-search', 'visibility']", lines[5])
        self.assertIn('events.log has 7 unparseable line(s); first at line 103', lines[6])
        # Four of them are the hand-written "2026-10-09 22:01 ..." lines.
        self.assertEqual(sum(1 for l in (FIX / 'events.log').read_text().splitlines() if re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d ', l)), 4)

    def test_ledger_length_boundary(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')])
        base = len((self.d / 'ledger.md').read_text().splitlines())
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], pad=60 - base)
        self.assertEqual(self.check('--offline')[0], 0)
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], pad=61 - base)
        code, lines, _ = self.check('--offline')
        self.assertEqual((code, self.rules(lines)), (1, ['ledger-length']))

    def test_next_action_rule(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1'), ('b', 'o2')], nexts=('o1',))
        self.make_run(rows=[('a', 'working'), ('b', 'working')], agents=[('a', 'o1'), ('b', 'o2')], nexts=('o1',))
        code, lines, _ = self.check('--offline')
        self.assertEqual((code, self.rules(lines)), (1, ['next-action']))
        self.assertTrue(lines[0].startswith('o2: '))
        text = (self.d / 'ledger.md').read_text().replace('Next action (o1): do the next thing', 'Next action (o1):\nNext action (o2):')
        (self.d / 'ledger.md').write_text(text)
        self.assertEqual(self.rules(self.check('--offline')[1]), ['next-action', 'next-action'])

    def test_row_registration_rules(self):
        self.make_run(rows=[('a', 'working'), ('ghost', 'working'), ('old', 'closed: done'), ('gone1', 'gone')],
                      agents=[('a', 'o1'), ('missing', 'o1')])
        code, lines, _ = self.check('--offline')
        self.assertEqual(sorted(self.rules(lines)), ['no-row', 'row-unregistered'])
        self.assertTrue(any('missing is registered but has no ledger row' in l for l in lines))
        self.assertTrue(any('ghost has a ledger row' in l for l in lines))
        # a mark-only name (an owner pane) is exempt
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], events=['2026-10-13T10:00:00Z o1 mark:handoff a1 | ctx 150k | proof -'])
        self.assertEqual(self.check('--offline')[0], 0)

    def test_not_closed_rule(self):
        self.make_run(rows=[('a', 'merged abc')], agents=[('a', 'o1')])
        self.assertIn('ledger row says merged', self.check('--offline')[1][0])
        self.make_run(rows=[('a', 'open: next cycle round 2')], agents=[('a', 'o1')])
        self.assertEqual(self.check('--offline')[0], 0)
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], events=['2026-10-13T10:00:00Z a mark:verified a1 | pass | proof p'])
        code, lines, _ = self.check('--offline')
        self.assertIn('marked verified', lines[0])
        # a later open or closed mark settles it; reported alone is not a done state
        self.log('2026-10-13T10:01:00Z a mark:open a1 | next cycle: more | proof -')
        self.assertEqual(self.check('--offline')[0], 0)
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], events=['2026-10-13T10:00:00Z a mark:reported a1 | says done | proof -'])
        self.assertEqual(self.check('--offline')[0], 0)
        # row says done, but the latest mark is a held open
        self.make_run(rows=[('a', 'done, kept')], agents=[('a', 'o1')], events=['2026-10-13T10:00:00Z a mark:open a1 | next cycle: more | proof -'])
        self.assertEqual(self.check('--offline')[0], 0)
        self.log('2026-10-13T10:05:00Z a working | t | ctx -')
        self.assertEqual(self.rules(self.check('--offline')[1]), ['not-closed'])

    def test_watcher_rules(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')])
        with patch.object(m, 'pid_alive', return_value=False):
            self.assertEqual(self.rules(self.check('--offline')[1]), ['watcher'])
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], watcher='pane wX:p1, agents: a (.orch/agents.txt)')
        self.assertIn('has no pid', self.check('--offline')[1][0])
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')], watcher=f'pane wX:p1, pid {os.getpid()}, agents: a, b (.orch/agents.txt), log: x')
        self.assertIn("['a', 'b'] but agents.txt holds ['a']", self.check('--offline')[1][0])

    def test_owner_liveness_and_offline(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')])
        self.agent('someone')
        code, lines, _ = self.check()
        self.assertEqual((code, self.rules(lines)), (1, ['owner-dead']))
        self.assertTrue(lines[0].startswith('o1: '))
        self.assertEqual(self.check('--offline')[0], 0)
        self.agent('o1')
        self.assertEqual(self.check()[0], 0)

    def test_owner_filter(self):
        self.make_run(rows=[('a', 'done'), ('b', 'done')], agents=[('a', 'o1'), ('b', 'o2')], nexts=('o1', 'o2'), pad=70)
        everything = self.check('--offline')[1]
        self.assertEqual(sorted(self.rules(everything)), ['ledger-length', 'not-closed', 'not-closed'])
        mine = self.check('--owner', 'o1', '--offline')[1]
        self.assertEqual(sorted(self.rules(mine)), ['ledger-length', 'not-closed'])
        self.assertTrue(all(l.startswith(('o1: ', 'run: ')) for l in mine))
        self.assertEqual(self.check('--owner', 'nobody', '--offline')[1], ['run: [ledger-length] ' + everything[0].split('] ')[1]])

    def test_cannot_parse_exits_3(self):
        code, _, err = self.check('--offline')
        self.assertEqual(code, 3)
        self.assertIn('ledger.md', err)
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')])
        good = (self.d / 'ledger.md').read_text()
        for broken, why in ((good.replace('## Pane agents', '## Agents'), 'no Pane agents table'),
                            (good.replace('## Watcher', '## Watching'), 'no Watcher section'),
                            (good.replace('| working |', '| working | extra |'), 'cells'),
                            (good.replace('| name |', '| who |'), 'header')):
            (self.d / 'ledger.md').write_text(broken)
            code, lines, err = self.check('--offline')
            self.assertEqual((code, lines), (3, []), why)
            self.assertIn(why.split()[-1], err)
        (self.d / 'ledger.md').write_text(good)
        (self.d / 'agents.txt').write_text('a orch=o1 junk\n')
        self.assertEqual(self.check('--offline')[0], 3)

    def test_cli_exit_codes(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')])
        self.assertEqual(self.run_cli('check', str(self.d), '--offline').returncode, 0)
        self.assertEqual(self.run_cli('check', str(self.d), '--offline', '--bogus').returncode, 2)
        self.make_run(rows=[('a', 'done')], agents=[('a', 'o1')])
        r = self.run_cli('check', str(self.d), '--offline')
        self.assertEqual(r.returncode, 1)
        self.assertIn('o1: [not-closed] a:', r.stdout)
        (self.d / 'ledger.md').unlink()
        self.assertEqual(self.run_cli('check', str(self.d), '--offline').returncode, 3)

    def test_hand_written_and_stray_log_lines(self):
        self.make_run(rows=[('a', 'working')], agents=[('a', 'o1')],
                      events=['2026-10-09 22:01 tartib-search done; suite re-run 399 passed; awaiting commit decision',
                              '2026-10-09T15:38:32Z lore closed by orch-3: lore plan complete'])
        code, lines, _ = self.check('--offline')
        self.assertEqual((code, self.rules(lines)), (1, ['log']))
        self.assertIn('2 unparseable line(s); first at line 1: 2026-10-09 22:01 tartib-search', lines[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
