import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
with mock.patch.object(sys, 'path', [str(SCRIPTS)] + sys.path):
    spec = importlib.util.spec_from_file_location('readiness', SCRIPTS / 'gserver_connection_readiness.py')
    readiness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(readiness)


class ReadinessTests(unittest.TestCase):
    def test_report_lists_slots_without_secrets(self):
        import io
        import contextlib
        buffer = io.StringIO()
        with mock.patch.object(sys, 'argv', ['readiness']), contextlib.redirect_stdout(buffer):
            code = readiness.main()
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn('READY_FOR_CREDENTIALS=REPORT_ONLY', output)
        self.assertIn('BOT_BRIDGE=/bot/events', output)
        self.assertNotIn('PrivateKey', output)

    def test_bundle_without_tunnel_credential_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            manifest = {'schema': 'gserver.vpn-bundle.v1', 'project': 'gace-vpn-0123456789abcdef',
                        'profile': {'path': '/x', 'region': 'jp', 'sha256': 'a' * 64},
                        'hashes': {'compose.json': 'b' * 64, 'guard.nft': 'c' * 64, 'wireguard.conf': 'd' * 64},
                        'components': ['vpn', 'app', 'cloudflared']}
            compose = {'services': {'vpn': {}, 'app': {}, 'cloudflared': {}}}
            (bundle / 'compose.json').write_text(json.dumps(compose))
            (bundle / 'manifest.json').write_text(json.dumps(manifest))
            with mock.patch.object(readiness.vpn, 'load', return_value=(bundle, manifest)):
                import io
                import contextlib
                buffer = io.StringIO()
                with mock.patch.object(sys, 'argv', ['readiness', '--bundle', str(bundle)]), \
                     contextlib.redirect_stdout(buffer):
                    readiness.main()
                self.assertIn('READY_FOR_CREDENTIALS=TUNNEL_CREDENTIAL_MISSING', buffer.getvalue())
