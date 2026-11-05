import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]/'scripts'
with mock.patch.object(sys,'path',[str(ROOT)]+sys.path):
 spec=importlib.util.spec_from_file_location('recovery',ROOT/'gserver_recovery_check.py')
 recovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
 def check(self, values):
  response=mock.MagicMock();response.__enter__.return_value.status=200
  client=mock.Mock();client.open.return_value=response
  stream=io.StringIO()
  with mock.patch.object(recovery.urllib.request,'build_opener',return_value=client),mock.patch.object(recovery,'run',side_effect=values) as run,contextlib.redirect_stdout(stream):
   code=recovery.main()
  return code,json.loads(stream.getvalue()),run

 def test_current_checks_pass_does_not_claim_automatic_boot_or_full_data_restore(self):
  code,result,run=self.check([json.dumps([{'State':{'Health':{'Status':'healthy'}}}]),json.dumps({'owner_storage':'PASS','sqlite_quick_check':'PASS','spool_rows':2})])
  self.assertEqual(code,0)
  self.assertEqual(result['automatic_windows_to_wsl_start'],'NOT_VERIFIED')
  self.assertEqual(result['pre_post_data_comparison'],'NOT_AVAILABLE')
  self.assertEqual(result['complete_restore_acceptance'],'NOT_COMPLETE')
  self.assertTrue(all('stop' not in c.args[0] and 'up' not in c.args[0] for c in run.call_args_list))

 def test_sqlite_corruption_refuses_pass(self):
  code,result,_=self.check([json.dumps([{'State':{'Health':{'Status':'healthy'}}}]),json.dumps({'owner_storage':'PASS','sqlite_quick_check':'FAIL','spool_rows':2})])
  self.assertEqual(code,1)
  self.assertEqual(result['current_recovery_checks'],'NOT_VERIFIED')

 def test_database_is_opened_read_only_without_claim_or_repair(self):
  self.assertIn('?mode=ro',recovery.CORE_CHECK)
  self.assertIn('PRAGMA query_only=ON',recovery.CORE_CHECK)
  for forbidden in ('BotSpool(', 'INSERT ', 'UPDATE ', 'DELETE ', 'VACUUM', 'wal_checkpoint'):
   self.assertNotIn(forbidden,recovery.CORE_CHECK)
