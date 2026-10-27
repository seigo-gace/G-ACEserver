"""Execute the actual smoke shell against a fake Docker boundary, without sudo."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_SUDO = '''#!/usr/bin/env python3
import os, pathlib, sys
a = sys.argv[1:]
root = pathlib.Path(os.environ['FAKE_ROOT'])
scenario = os.environ['SCENARIO']
with (root / 'calls').open('a') as f: f.write(' '.join(a) + '\\n')
if a == ['-v']: sys.exit(0)
a = a[a.index('docker') + 1:]
if a[:2] == ['volume', 'ls'] and scenario == 'existing': print('existing-volume')
if a[0] == 'build':
 pathlib.Path(a[a.index('--iidfile')+1]).write_text('sha256:' + 'a'*64)
if a[0] == 'inspect': print('none')
if a[0] == 'compose':
 command = a[a.index('-f')+2]
 if command == 'up':
  if scenario == 'start_failure': sys.exit(20)
  n = root / 'count'; n.write_text(str(int(n.read_text())+1 if n.exists() else 1))
 if command == 'ps': print('container-' + (root / 'count').read_text())
 if command == 'down' and scenario == 'cleanup_failure': sys.exit(9)
'''


class RuntimeSmokeTests(unittest.TestCase):
    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sudo').write_text(FAKE_SUDO)
            (root / 'sudo').chmod(0o755)
            (root / 'systemctl').write_text('#!/bin/sh\nprintf "active\\n"\n')
            (root / 'systemctl').chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ['PATH'],
                       FAKE_ROOT=directory, SCENARIO=scenario)
            result = subprocess.run(['bash', str(ROOT / 'scripts/smoke_gserver_runtime.sh')],
                                    env=env, capture_output=True, text=True, timeout=20)
            return result, (root / 'calls').read_text()

    def test_existing_volume_refuses_build_and_teardown(self):
        result, calls = self.run_scenario('existing')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('docker build', calls)
        self.assertNotIn(' down ', calls)

    def test_start_failure_captures_logs_before_teardown(self):
        result, calls = self.run_scenario('start_failure')
        self.assertEqual(result.returncode, 20)
        self.assertIn('VERIFY=FAIL', result.stdout)
        self.assertLess(calls.index(' logs '), calls.index(' down '))

    def test_cleanup_failure_cannot_report_pass(self):
        result, calls = self.run_scenario('cleanup_failure')
        self.assertEqual(result.returncode, 33)
        self.assertNotIn('VERIFY=PASS', result.stdout)

    def test_success_recreates_and_removes_only_isolated_volume(self):
        result, calls = self.run_scenario('success')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--force-recreate', calls)
        self.assertIn('down --volumes --timeout 10', calls)
        self.assertIn('gace-gserver-runtime-smoke', calls)
        self.assertNotIn('prune', calls)


if __name__ == '__main__':
    unittest.main()
