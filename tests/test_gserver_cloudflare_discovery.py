"""Read-only discovery must fail closed before copying account credentials."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gserver_cloudflare_discovery as cf
import gserver_vpn as vpn

TARGET = '11111111-1111-4111-8111-111111111111'
IMAGE = 'cloudflare/cloudflared@sha256:' + 'a' * 64
SECRET = 'synthetic-private-value'
CERT = b'-----BEGIN ARGO TUNNEL TOKEN-----\n' + base64.b64encode(json.dumps(
    {'accountID': 'account', 'zoneID': 'zone', 'apiToken': SECRET}).encode()) + b'\n-----END ARGO TUNNEL TOKEN-----'


class DiscoverySafety(unittest.TestCase):
    def identity(self):
        return {'certificate': CERT, 'certificate_sha256': 'hash', 'account_id': 'account',
                'zone_id': 'zone', 'targets': [TARGET]}

    def test_acl_failure_precedes_reading_or_conversion(self):
        result = types.SimpleNamespace(stdout='{"Protected":false}')
        with mock.patch.object(cf.subprocess, 'run', return_value=result) as run, \
             mock.patch.object(Path, 'read_bytes') as read:
            with self.assertRaisesRegex(vpn.VPNError, 'WINDOWS_ORIGIN_CERT_ACL_UNVERIFIED'):
                cf.windows_identity()
        self.assertEqual(run.call_count, 1)
        read.assert_not_called()

    def test_metadata_error_never_echoes_native_diagnostic(self):
        with mock.patch.object(cf.subprocess, 'run', side_effect=OSError(SECRET)):
            with self.assertRaisesRegex(vpn.VPNError, '^WINDOWS_ORIGIN_CERT_METADATA_UNAVAILABLE$'):
                cf.windows_identity()

    def test_local_identity_matches_account_and_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / (TARGET + '.json')
            for account in ('other-account', 'account'):
                path.write_text(json.dumps({'TunnelID': TARGET, 'AccountTag': account, 'TunnelSecret': SECRET}))
                if account == 'account':
                    self.assertEqual(cf.parse_identity(root, CERT)['targets'], [TARGET])
                else:
                    with self.assertRaisesRegex(vpn.VPNError, 'MATCHING_LOCAL_TUNNEL_CREDENTIAL_MISSING'):
                        cf.parse_identity(root, CERT)

    def test_malformed_certificate_does_not_echo_secret(self):
        for value in (SECRET.encode(), b'-----BEGIN ARGO TUNNEL TOKEN-----\ne30=\n-----END ARGO TUNNEL TOKEN-----'):
            with self.assertRaisesRegex(vpn.VPNError, '^WINDOWS_TUNNEL_IDENTITY_INVALID$'):
                cf.parse_identity(Path('/unused'), value)

    def test_symlink_credential_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / (TARGET + '.json')).symlink_to('/nonexistent')
            with self.assertRaisesRegex(vpn.VPNError, 'WINDOWS_TUNNEL_IDENTITY_INVALID'):
                cf.parse_identity(root, CERT)

    def invoke(self, response=None, error=None):
        if response is None:
            response = [{'id': TARGET, 'name': 'existing-tunnel', 'connections': [{'origin_ip': SECRET}]}]
        with mock.patch.object(vpn, 'stage_tunnel_credential') as stage, \
             mock.patch.object(cf, 'docker', return_value=json.dumps(response), side_effect=error) as run:
            result = cf.discover(Path('/dev/shm/private'), 'vpn-id', 'project', IMAGE, identity=self.identity())
        return result, run.call_args.args, stage

    def test_only_id_filtered_native_list_uses_guarded_network_and_private_mount(self):
        result, command, stage = self.invoke()
        self.assertEqual(command[command.index(IMAGE) + 1:],
                         ('tunnel', '--origincert', vpn.ORIGIN_CONTAINER_FILE, 'list', '--output', 'json', '--id', TARGET))
        self.assertEqual(command[command.index('--network') + 1], 'container:vpn-id')
        self.assertEqual(command[command.index('--user') + 1], '65534:65534')
        self.assertIn('--read-only', command)
        self.assertNotIn(SECRET, repr(command))
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(result['tunnels'][0]['connections'], 1)
        self.assertEqual(stage.call_args.kwargs, {'kind': 'origin-cert'})

    def test_unrelated_resource_and_malformed_provider_response_are_rejected(self):
        for response in ({}, [], [{'id': 'unrelated'}], [{'id': TARGET, 'name': 123}],
                         [{'id': TARGET, 'name': 'x', 'connections': 'invalid'}]):
            with self.subTest(response=response), self.assertRaisesRegex(vpn.VPNError, 'CLOUDFLARE_DISCOVERY_RESPONSE_INVALID'):
                self.invoke(response)

    def test_provider_failure_never_carries_raw_diagnostics(self):
        error = cf.AppError('DOCKER_COMMAND_FAILED')
        error.diagnostic = SECRET
        with self.assertRaisesRegex(vpn.VPNError, '^CLOUDFLARE_DISCOVERY_COMMAND_FAILED$') as caught:
            self.invoke(error=error)
        self.assertFalse(getattr(caught.exception, 'diagnostic', ''))

    def test_origin_staging_uses_fixed_file_and_stdin(self):
        with mock.patch.object(vpn, 'run', return_value='{"ok":true}') as run:
            vpn.stage_tunnel_credential(Path('/dev/shm/private'), CERT, kind='origin-cert')
        self.assertNotIn(SECRET, repr(run.call_args.args))
        self.assertNotIn(base64.b64encode(SECRET.encode()).decode(), repr(run.call_args.args))
        self.assertEqual(run.call_args.kwargs['input'], CERT.decode())
        with self.assertRaisesRegex(vpn.VPNError, 'TUNNEL_CREDENTIAL_KIND_INVALID'):
            vpn.stage_tunnel_credential(Path('/unused'), CERT, kind='arbitrary-path')

    def test_helper_creates_only_origin_fixed_name_with_private_mode(self):
        info = types.SimpleNamespace(st_uid=1000, st_mode=stat.S_IFDIR | 0o700)
        with mock.patch.object(sys, 'argv', ['helper', 'private', '1000', 'origin-cert']), \
             mock.patch.object(sys, 'stdin', types.SimpleNamespace(buffer=io.BytesIO(CERT))), \
             mock.patch.dict(os.environ, {'SUDO_UID': '1000'}), \
             mock.patch('os.open', side_effect=[9, 10]) as opened, \
             mock.patch('os.fstat', return_value=info), mock.patch('os.write', return_value=len(CERT)), \
             mock.patch('subprocess.run', return_value=types.SimpleNamespace(stdout='tmpfs\n')), \
             mock.patch('os.fchown') as chown, mock.patch('os.fchmod') as chmod, \
             mock.patch('os.fsync'), mock.patch('os.close'), contextlib.redirect_stdout(io.StringIO()) as output:
            exec(vpn.TUNNEL_STAGE_HELPER, {})
        self.assertEqual(json.loads(output.getvalue()), {'ok': True})
        self.assertEqual(opened.call_args_list[1].args[0], vpn.ORIGIN_RUNTIME_FILE)
        chown.assert_called_once_with(10, 65534, 65534)
        chmod.assert_called_once_with(10, 0o400)

    def test_receipt_is_owner_only_and_rejects_public_directory(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(Path, 'home', return_value=Path(directory)):
            cf.save_receipt({'scope': 'metadata-only'})
            root = Path(directory) / '.local/state/gserver/verification'
            self.assertEqual(stat.S_IMODE((root / 'cloudflare-discovery.json').stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            root.chmod(0o755)
            with self.assertRaisesRegex(vpn.VPNError, 'DISCOVERY_RECEIPT_DIRECTORY_UNSAFE'):
                cf.save_receipt({})


class DiscoveryLifecycle(unittest.TestCase):
    def test_acl_failure_creates_no_docker_objects(self):
        import smoke_gserver_vpn_live as live
        with mock.patch.dict(os.environ, {'GSERVER_VPN_REGION': 'jp', 'GSERVER_CLOUDFLARE_DISCOVERY': '1',
                                         'GSERVER_CLOUDFLARED_CREDENTIAL': '', 'GSERVER_VPN_LEARN_BACKUP': ''}), \
             mock.patch.object(cf, 'windows_identity', side_effect=vpn.VPNError('WINDOWS_ORIGIN_CERT_ACL_UNVERIFIED')), \
             mock.patch.object(live, 'docker') as docker, mock.patch.object(live, 'inventory') as inventory, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live.main(), 1)
        docker.assert_not_called()
        inventory.assert_not_called()
        self.assertNotIn('ACCEPTANCE_LIVE_VPN=PASS', output.getvalue())

    def test_discovery_receipt_requires_kill_switch_and_cleanup(self):
        from tests.test_smoke_gserver_vpn_live_contract import LiveLifecycleEvidence, live
        for kwargs, accepted in (({}, True), ({'tcp': [True, True]}, False), ({'cleanup_fail': True}, False)):
            with self.subTest(kwargs=kwargs), \
                 mock.patch.object(live.discovery, 'windows_identity', return_value={}), \
                 mock.patch.object(live.discovery, 'discover', return_value={'tunnels': [{'id': TARGET}]}) as read, \
                 mock.patch.object(live.discovery, 'save_receipt') as save:
                code, output, calls = LiveLifecycleEvidence().exercise(cloudflare=True, **kwargs)
            read.assert_called_once()
            self.assertEqual(save.call_count, int(accepted))
            self.assertEqual(code, 0 if accepted else 1)
            self.assertIn('ACCEPTANCE_CLOUDFLARE=NOT_RUN', output)
            self.assertNotIn(TARGET, output)
