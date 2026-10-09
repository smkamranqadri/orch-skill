"""Statusline payload fixtures follow the installed mod's rate_limits schema."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('usage', ROOT/'skills/orch/scripts/orch-usage.py')
u=importlib.util.module_from_spec(spec); spec.loader.exec_module(u)
NOW=10000

class CmdUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name); self.path=self.d/'usage-cmd.json'
        env={k:v for k,v in os.environ.items() if not k.startswith('HERDR_') and k!='CMD_API_KEY'}
        env.update(ORCH_USAGE_CACHE_DIR=str(self.d))
        p=patch.dict(os.environ,env,clear=True); p.start(); self.addCleanup(p.stop)
        p=patch.object(u.time,'time',return_value=NOW); p.start(); self.addCleanup(p.stop)
        p=patch.object(u.urllib.request,'urlopen',side_effect=AssertionError('network must be mocked'))
        self.network=p.start(); self.addCleanup(p.stop)

    def fixture(self, age=0, **extra):
        self.raw={'cli':'cmd','fetched_at':NOW-age,'model':'deepseek/deepseek-v4-flash',
                  'rate_limits': {'five_hour': {'used_percentage':12.4,'resets_at':NOW+3600},
                                  'seven_day': {'used_percentage':85.2,'resets_at':NOW+86400}}}
        self.raw.update(extra); self.path.write_text(json.dumps(self.raw))

    def test_fresh_stale_boundary(self):
        self.fixture(age=299); self.assertEqual(u.read_cmd(str(self.d),True)['status'],'ok')
        self.fixture(age=300); self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')
        self.fixture(age=301); self.assertEqual(u.read_cmd(str(self.d),False)['status'],'unknown')
        self.network.assert_not_called()

    def test_cache_over_key(self):
        self.fixture(); before=self.path.read_bytes()
        with patch.dict(os.environ,CMD_API_KEY='fixture-only-key'):
            for cached in (False,True):
                got=u.read_cmd(str(self.d),cached)
                self.assertEqual(got['five_hour']['used_pct'],12)
                self.assertEqual(got['seven_day']['used_pct'],85)
            self.network.assert_not_called()
        self.assertEqual(self.path.read_bytes(),before)

    def test_unknown_and_malformed(self):
        self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')
        for raw in [[],{}, {'fetched_at':NOW,'rate_limits':{}},
                    {'fetched_at':NOW+1,'rate_limits':{'five_hour':{'used_percentage':1}}},
                    {'fetched_at':NOW,'rate_limits':{'five_hour':{'used_percentage':'bad'}}}]:
            self.path.write_text(json.dumps(raw))
            self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')
        self.path.write_text('{broken')
        self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')

    def test_reset_and_percent_guard(self):
        self.fixture(); self.raw['rate_limits']['five_hour']['resets_at']=NOW
        self.path.write_text(json.dumps(self.raw)); self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')
        self.fixture(); self.raw['rate_limits']['five_hour']['used_percentage']=101
        self.path.write_text(json.dumps(self.raw)); self.assertEqual(u.read_cmd(str(self.d),True)['status'],'unknown')

    def test_check_and_board_line(self):
        self.fixture()
        with patch.object(u.sys,'stdout',new_callable=io.StringIO) as out:
            self.assertEqual(u.main(['check','cmd','--cached']),3)
            self.assertIn('cmd: 85% used',out.getvalue())
        snapshot=u.last()
        self.assertIn('cmd 12%/85% ASK',u.line(snapshot))
        self.assertIn('cmd    5h 12%',u.show(snapshot))
        self.fixture(age=300)
        with patch.object(u.sys,'stdout',new_callable=io.StringIO):
            self.assertEqual(u.main(['check','cmd','--cached']),2)
        self.assertIn('cmd ?',u.line(u.last()))

    def test_api_cache_is_separate(self):
        self.fixture(age=300); before=self.path.read_bytes()
        payload={'windowLimits':{'fiveHour':{'used':1,'cap':10,'resetAt':NOW+3600},
                                'weekly':{'used':2,'cap':10,'resetAt':NOW+86400}}}
        self.network.side_effect=None; self.network.return_value=io.StringIO(json.dumps(payload))
        with patch.dict(os.environ,CMD_API_KEY='fixture-only-key'):
            self.assertEqual(u.read_cmd(str(self.d),False)['five_hour']['used_pct'],10)
            self.assertEqual(u.read_cmd(str(self.d),True)['seven_day']['used_pct'],20)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue((self.d/'usage-cmd-api.json').exists())

    def test_statusline_block(self):
        # Run the exact block delivered in the handoff, only with a temporary cache directory.
        self.fixture(); self.path.unlink()
        block=(ROOT/'skills/orch/references/cmd-statusline-cache.sh').read_text()
        script='input=$(cat)\nLIM5=12.4\nLIM7=85.2\n'+block
        payload=dict(self.raw, model={'display_name':self.raw['model']})
        r=subprocess.run(['bash','-c',script],input=json.dumps(payload),capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(r.stdout,'')
        got=json.loads(self.path.read_text())
        self.assertEqual(got['rate_limits'],self.raw['rate_limits'])
        self.assertEqual(got['cli'],'cmd'); self.assertIsInstance(got['fetched_at'],int)
        self.assertEqual(list(self.d.glob('usage-cmd.json.*')),[])

if __name__=='__main__': unittest.main(verbosity=2)
