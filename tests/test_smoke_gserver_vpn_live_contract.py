"""Static safety checks and preflight logic for the VPN live smoke harness."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SCRIPT = ROOT / 'scripts' / 'smoke_gserver_vpn_live.py'
spec = importlib.util.spec_from_file_location('vpn_live', SCRIPT)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
import gserver_vpn as vpn


class VpnLiveSmokeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = SCRIPT.read_text()

    def test_no_secret_output_markers(self):
        for forbidden in ('api.ipify', 'Bearer ', 'PrivateKey', 'secret_token', 'print(data',
                          'print(token', 'PUBLIC_IP='):
            self.assertNotIn(forbidden, self.body)

    def test_envelope_and_core_protection(self):
        for marker in ('GACE_RESULT_BEGIN', 'CORE_NOT_HEALTHY', 'CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS',
                       'WIREGUARD_CONNECTION=PASS', 'KILL_SWITCH', 'CLOUDFLARE'):
            self.assertIn(marker, self.body)

    def test_uses_gluetun_local_publicip_api(self):
        self.assertIn('127.0.0.1:8000/v1/publicip/ip', self.body)

    def test_failure_code_not_redacted_to_value(self):
        self.assertIn('LIVE_FAILURE_CODE=', self.body)
        self.assertNotIn('LIVE_FAILURE_DETAIL=', self.body)


class LivePreflightRegion(unittest.TestCase):
    def base_status(self):
        return {
            'docker_access': 'OK',
            'vpn': 'LOCAL_PINNED_IMAGE_PRESENT',
            'app': 'LOCAL_PINNED_IMAGE_PRESENT',
            'cloudflared': 'LOCAL_PINNED_IMAGE_PRESENT',
            'endpoint_cache': 'OK',
            'endpoint_pin_jp': 'NOT_CONFIGURED',
            'endpoint_pin_kr': 'NOT_CONFIGURED',
        }

    def test_jp_run_allows_kr_pin_missing(self):
        status = self.base_status()
        status['endpoint_pin_jp'] = 'CONFIGURED'
        live.validate_live_preflight(status, 'jp')

    def test_jp_run_rejects_missing_jp_pin(self):
        status = self.base_status()
        status['endpoint_pin_kr'] = 'CONFIGURED'
        with self.assertRaises(vpn.VPNError) as error:
            live.validate_live_preflight(status, 'jp')
        self.assertEqual(str(error.exception), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')

    def test_kr_run_allows_jp_pin_missing(self):
        status = self.base_status()
        status['endpoint_pin_kr'] = 'CONFIGURED'
        live.validate_live_preflight(status, 'kr')

    def test_kr_run_rejects_missing_kr_pin(self):
        status = self.base_status()
        status['endpoint_pin_jp'] = 'CONFIGURED'
        with self.assertRaises(vpn.VPNError) as error:
            live.validate_live_preflight(status, 'kr')
        self.assertEqual(str(error.exception), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')


class LiveFailureDetail(unittest.TestCase):
    def test_vpn_error_code_preserved(self):
        exc = vpn.VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')
        self.assertEqual(live.live_failure_detail(exc), 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')

    def test_unstructured_message_sanitized(self):
        token = 'x' * 40
        detail = live.live_failure_detail(RuntimeError('boom ' + token))
        self.assertNotIn(token, detail)
        self.assertIn('<value>', detail)


if __name__ == '__main__':
    unittest.main()
