"""Static safety checks for the VPN/cloudflared live smoke harness."""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'smoke_gserver_vpn_live.py'


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


if __name__ == '__main__':
    unittest.main()
