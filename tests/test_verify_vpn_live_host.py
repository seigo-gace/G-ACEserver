"""Execute the real shell wrapper with deterministic command stubs, never Docker."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_vpn_live_host.sh'


class SequentialVpnWrapper(unittest.TestCase):
    def run_wrapper(self, args=(), fail_jp=False, region='kr'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'calls'
            python = root / 'python3'
            python.write_text('''#!/bin/bash
if [[ "$*" == *smoke_gserver_vpn_live.py* ]]; then
    printf '%s:%s\\n' "${GSERVER_VPN_REGION:-}" "${GSERVER_VPN_LEARN_BACKUP:-}" >> "$CASE_LOG"
    if [[ "${GSERVER_VPN_REGION:-}" == jp && "$FAIL_JP" == 1 ]]; then exit 7; fi
fi
''')
            sudo = root / 'sudo'
            sudo.write_text('#!/bin/bash\nexit 0\n')
            python.chmod(0o700)
            sudo.chmod(0o700)
            env = {**os.environ, 'PATH': str(root) + ':' + os.environ['PATH'],
                   'CASE_LOG': str(log), 'FAIL_JP': '1' if fail_jp else '0',
                   'GSERVER_VPN_REGION': region, 'GSERVER_VPN_LEARN_BACKUP': ''}
            result = subprocess.run(['bash', str(SCRIPT), *args], env=env, capture_output=True, timeout=10)
            calls = log.read_text().splitlines() if log.exists() else []
            return result.returncode, calls

    def test_both_runs_jp_then_kr_with_learning_only_on_jp(self):
        self.assertEqual(self.run_wrapper(('--both',)), (0, ['jp:kr', 'kr:']))

    def test_jp_failure_prevents_any_kr_run(self):
        self.assertEqual(self.run_wrapper(('--both',), fail_jp=True), (7, ['jp:kr']))

    def test_default_keeps_selected_single_region(self):
        self.assertEqual(self.run_wrapper(), (0, ['kr:']))

    def test_local_cloudflare_mode_runs_no_live_vpn(self):
        self.assertEqual(self.run_wrapper(('--cloudflare-local',)), (0, []))

    def test_unknown_arguments_fail_before_testing_or_runtime(self):
        self.assertEqual(self.run_wrapper(('--unknown',)), (2, []))
