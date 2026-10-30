import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/gserver_vpn.py'
spec = importlib.util.spec_from_file_location('vpn', SCRIPT)
vpn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vpn)
KEY = base64.b64encode(b'a'*32).decode()
VPN_IMAGE = 'qmcgaw/gluetun@sha256:' + '1'*64
APP_IMAGE = 'sha256:' + '2'*64
TUNNEL_IMAGE = 'cloudflare/cloudflared@sha256:' + '3'*64
PROFILE = f'''[Interface]
PrivateKey = {KEY}
Address = 10.10.0.2/32
DNS = 10.255.255.3
[Peer]
PublicKey = {KEY}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 93.184.216.34:51820
PersistentKeepalive = 25
'''


class VPNTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / vpn.REGIONS['jp']
        self.write(PROFILE)

    def write(self, text):
        self.path.write_text(text)
        self.path.chmod(0o600)

    def bundle(self):
        out = self.root / 'private-bundle'
        return out, vpn.render(out, 'jp', self.path, VPN_IMAGE, APP_IMAGE)

    def test_valid_profile_is_not_connection_acceptance(self):
        value = vpn.profile(self.path, 'jp')
        self.assertEqual(value['port'], 51820)
        self.assertNotIn(KEY, json.dumps(value))

    def test_rejects_public_secret_permissions(self):
        self.path.chmod(0o644)
        with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')

    def test_rejects_secret_symlinks(self):
        original = self.path.rename(self.root / 'other')
        self.path.symlink_to(original)
        with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')

    def test_rejects_hooks_and_config_side_effects(self):
        for key in ('PostUp', 'PreUp', 'PostDown', 'SaveConfig', 'Table'):
            with self.subTest(key=key):
                self.write(PROFILE.replace('[Peer]', key+' = anything\n[Peer]'))
                with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')

    def test_endpoint_cannot_be_private_or_ipv6(self):
        for endpoint in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '[2001:4860:4860::8888]'):
            with self.subTest(endpoint=endpoint):
                self.write(PROFILE.replace('93.184.216.34', endpoint))
                with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')


    def test_real_provider_dual_stack_and_hostname_are_supported_without_dns(self):
        self.write(PROFILE.replace('10.10.0.2/32','10.10.0.2/32, fd00::2/128').replace('93.184.216.34','vpn.example.com'))
        with mock.patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')):
            self.assertEqual(vpn.profile(self.path,'jp')['endpoint'], 'vpn.example.com')
            with mock.patch.object(vpn, 'endpoint_pins', return_value={}):
                with self.assertRaisesRegex(vpn.VPNError, 'ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED'):
                    vpn.render(self.root/'no-pin','jp',self.path,VPN_IMAGE,APP_IMAGE)
            out=self.root/'pinned'
            vpn.render(out,'jp',self.path,VPN_IMAGE,APP_IMAGE,'93.184.216.34')
        runtime=(out/'wireguard.conf').read_text()
        self.assertIn(KEY,runtime)
        self.assertNotIn('DNS', runtime)
        self.assertNotIn('fd00::',runtime)
        self.assertNotIn('::/0',runtime)
        self.assertNotIn('vpn.example.com',runtime)
        self.assertIn('fd00::',self.path.read_text())

    def test_invalid_keys_have_secret_safe_error(self):
        self.write(PROFILE.replace(KEY, 'not-a-key-secret'))
        with self.assertRaises(vpn.VPNError) as error: vpn.profile(self.path, 'jp')
        self.assertNotIn('not-a-key-secret', str(error.exception))

    def test_requires_default_route_and_matching_region(self):
        with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'kr')
        self.write(PROFILE.replace('0.0.0.0/0, ::/0', '10.0.0.0/8'))
        with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')

    def test_partial_profile_rejected(self):
        self.write(PROFILE.replace('DNS = 10.255.255.3\n', ''))
        with self.assertRaises(vpn.VPNError): vpn.profile(self.path, 'jp')

    def test_mutable_images_rejected_before_output_creation(self):
        with self.assertRaises(vpn.VPNError):
            vpn.render(self.root/'bad', 'jp', self.path, 'qmcgaw/gluetun:latest', APP_IMAGE)
        self.assertFalse((self.root/'bad').exists())

    def test_private_bundle_does_not_embed_wg_keys(self):
        out, manifest = self.bundle()
        for p in out.iterdir():
            if p.name != 'wireguard.conf':
                self.assertNotIn(KEY, p.read_text())
            self.assertEqual(p.stat().st_mode & 0o077, 0)
        self.assertEqual(set(manifest['acceptance'].values()), {'NOT_VERIFIED'})

    def test_cloudflared_shares_vpn_without_compose_secrets(self):
        out = self.root / 'tunnel-bundle'
        vpn.render(out, 'jp', self.path, VPN_IMAGE, APP_IMAGE, cloudflared_image=TUNNEL_IMAGE)
        config = json.loads((out / 'compose.json').read_text())
        tunnel = config['services']['cloudflared']
        self.assertEqual(tunnel['network_mode'], 'service:vpn')
        self.assertNotIn('environment', tunnel)
        blob = json.dumps(config)
        self.assertNotIn('eyJ', blob)
        self.assertIn('/run/gserver-tunnel/credential', blob)

    def test_gluetun_vpn_not_read_only_app_sidecars_are(self):
        out, _ = self.bundle()
        config = json.loads((out / 'compose.json').read_text())
        self.assertNotIn('read_only', config['services']['vpn'])
        self.assertTrue(config['services']['app']['read_only'])

    def test_apps_cannot_change_namespace_and_have_no_direct_network(self):
        out, _ = self.bundle()
        config = json.loads((out/'compose.json').read_text())
        app, gateway = config['services']['app'], config['services']['vpn']
        self.assertEqual(app['network_mode'], 'service:vpn')
        self.assertEqual(app['cap_drop'], ['ALL'])
        self.assertNotIn('cap_add', app)
        self.assertEqual(app['user'], '65534:65534')
        self.assertNotIn('ports', gateway)
        self.assertNotIn('volumes', gateway)
        self.assertEqual(config['configs']['vpn_dns']['content'].splitlines()[0], 'nameserver 127.0.0.1')
        self.assertEqual(gateway['cap_add'], ['NET_ADMIN'])
        health = gateway['healthcheck']['test']
        self.assertIn('/run/gserver-guard/ready', ' '.join(health))
        self.assertIn('start_period', gateway['healthcheck'])
        self.assertEqual(gateway['restart'], 'no')
        self.assertIn('gserver-guard/ready', gateway['entrypoint'][-1])
        self.assertEqual(gateway['environment']['FIREWALL'], 'on')
        self.assertIn('/32', gateway['environment']['FIREWALL_OUTBOUND_SUBNETS'])
        self.assertEqual(gateway['environment']['DNS_SERVER'], 'on')
        self.assertEqual(gateway['environment']['WIREGUARD_ENDPOINT_PORT'], '51820')
        self.assertNotIn('DOT', gateway['environment'])
        self.assertNotIn('VPN_ENDPOINT_IP', gateway['environment'])

    def test_gluetun_log_summary_skips_banner_and_keeps_errors(self):
        raw = '@@@ banner @@@\n2026-01-01 ERROR cannot bind wireguard: test\n'
        summary = vpn.gluetun_log_summary(raw)
        self.assertIn('ERROR', summary)
        self.assertNotIn('@@@', summary)

    def test_sanitize_diagnostic_redacts_long_tokens(self):
        raw = 'compose_up_vpn_wait_healthy: error PrivateKey=abc ' + ('x' * 40)
        cleaned = vpn.sanitize_diagnostic(raw)
        self.assertIn('compose_up_vpn_wait_healthy', cleaned)
        self.assertNotIn('x' * 40, cleaned)
        self.assertIn('<redacted>', cleaned)

    def test_direct_dns_ipv6_and_wan_are_not_generally_allowed(self):
        rules = vpn.guard_rules('93.184.216.34', 51820)
        self.assertIn('policy drop', rules)
        self.assertIn('127.0.0.11 udp dport 53 drop', rules)
        self.assertNotIn('ct state established', rules)
        physical = [line for line in rules.splitlines() if 'eth0' in line]
        self.assertEqual(len(physical), 1)
        self.assertIn('udp dport 51820', physical[0])
        self.assertIn('meta nfproto ipv4 accept', rules)
        self.assertNotIn('meta nfproto ipv6 accept', rules)

    def test_bundle_and_profile_tampering_refused(self):
        out, _ = self.bundle()
        self.assertEqual(vpn.load(out)[0], out)
        (out/'guard.nft').write_text('unsafe')
        with self.assertRaises(vpn.VPNError): vpn.load(out)

    def test_profile_change_after_render_refused(self):
        out, _ = self.bundle()
        self.write(PROFILE.replace('51820', '51821'))
        with self.assertRaises(vpn.VPNError): vpn.load(out)

    def test_existing_directory_is_never_overwritten(self):
        out, _ = self.bundle()
        with self.assertRaises(FileExistsError): vpn.render(out, 'jp', self.path, VPN_IMAGE, APP_IMAGE)

    def exercise_start(self, fail_guard=False, existing=False):
        out, manifest = self.bundle()
        calls = []
        def run(cmd, **kwargs):
            calls.append(cmd)
            if 'ps' in cmd:
                if '-aq' in cmd: return 'old' if existing else ''
                return 'probe-container'
            if vpn.NAMESPACE_HELPER in cmd:
                if 'install' in cmd and fail_guard: raise vpn.VPNError('TEST_GUARD_FAILURE')
                return json.dumps({'ok':True,'inode':2,'nft':{'nftables':[]}})
            if 'inspect' in cmd and 'image' not in cmd:
                return json.dumps([{'State': {'Pid': 4242, 'Running': True, 'Health': {'Status': 'healthy'}},
                                    'Config': {'Labels': {'com.docker.compose.project': manifest['project']}}}])
            return ''
        def namespace(path, *args, **kwargs):
            return types.SimpleNamespace(st_ino=1 if str(path)=='/proc/1/ns/net' else 2)
        with mock.patch.object(vpn, 'load', return_value=(out,manifest)), \
             mock.patch.object(vpn, 'run', side_effect=run), mock.patch.object(vpn.os, 'stat', side_effect=namespace):
            if fail_guard or existing:
                with self.assertRaises(vpn.VPNError): vpn.start(out)
            else:
                self.assertEqual(vpn.start(out), 'STARTED_ACCEPTANCE_NOT_VERIFIED')
        return calls

    def test_guard_is_installed_before_vpn_release_and_app_start(self):
        calls = self.exercise_start()
        guard = next(i for i,c in enumerate(calls) if vpn.NAMESPACE_HELPER in c and 'install' in c)
        release = next(i for i,c in enumerate(calls) if 'touch /run/gserver-guard/ready' in c)
        app = next(i for i,c in enumerate(calls) if '--wait' in c and c[-1]=='app')
        self.assertLess(guard, release)
        self.assertLess(release, app)
        self.assertFalse(any('pull' in c or 'build' in c for c in calls))

    def test_guard_failure_stops_only_new_project_and_never_releases_marker(self):
        calls = self.exercise_start(fail_guard=True)
        self.assertTrue(any('stop' in c for c in calls))
        self.assertFalse(any('exec' in c for c in calls))
        self.assertFalse(any('gace-gserver' in c for c in calls))
        self.assertFalse(any('down' in c or '--volumes' in c for c in calls))

    def test_existing_project_is_refused_before_start(self):
        calls = self.exercise_start(existing=True)
        self.assertFalse(any('up' in c or 'stop' in c for c in calls))

    def test_privileged_helper_rejects_host_namespace_before_nft(self):
        import sys
        with mock.patch.object(sys,'argv',['helper','install','42','guard.nft']), \
             mock.patch('os.open',return_value=9), mock.patch('os.fstat',return_value=types.SimpleNamespace(st_ino=1)), \
             mock.patch('os.stat',return_value=types.SimpleNamespace(st_ino=1)), mock.patch('os.close'), \
             mock.patch('subprocess.run') as runner, contextlib.redirect_stdout(io.StringIO()) as output:
            exec(vpn.NAMESPACE_HELPER,{})
        self.assertFalse(json.loads(output.getvalue())['ok'])
        runner.assert_not_called()

    def test_privileged_helper_pins_namespace_fd(self):
        import sys
        result=types.SimpleNamespace(stdout='{"nftables":[]}',returncode=0)
        with mock.patch.object(sys,'argv',['helper','install','42','guard.nft']), \
             mock.patch('os.open',return_value=9), mock.patch('os.fstat',return_value=types.SimpleNamespace(st_ino=2)), \
             mock.patch('os.stat',return_value=types.SimpleNamespace(st_ino=1)), mock.patch('os.close') as close, \
             mock.patch('subprocess.run',return_value=result) as runner, contextlib.redirect_stdout(io.StringIO()) as output:
            exec(vpn.NAMESPACE_HELPER,{})
        self.assertTrue(json.loads(output.getvalue())['ok'])
        self.assertEqual(runner.call_count,2)
        for call in runner.call_args_list:
            self.assertIn('--net=/proc/self/fd/9',call.args[0])
            self.assertEqual(call.kwargs['pass_fds'],(9,))
        close.assert_called_once_with(9)

    def test_policy_fingerprint_ignores_only_counters_and_handles(self):
        a={'nft':{'nftables':[{'rule':{'handle':1,'expr':[{'counter':{'packets':0,'bytes':0}},{'drop':None}]}}]}}
        b={'nft':{'nftables':[{'rule':{'handle':2,'expr':[{'counter':{'packets':5,'bytes':100}},{'drop':None}]}}]}}
        self.assertEqual(vpn.policy_fingerprint(a),vpn.policy_fingerprint(b))
        b['nft']['nftables'][0]['rule']['expr'][-1]={'accept':None}
        self.assertNotEqual(vpn.policy_fingerprint(a),vpn.policy_fingerprint(b))

    def test_endpoint_cache_validation_without_printing_pins(self):
        cache = self.root / 'endpoint-cache.json'
        cache.write_text('{"jp": "93.184.216.34", "kr": "93.184.216.35"}')
        cache.chmod(0o600)
        with mock.patch.object(vpn, 'ENDPOINT_CACHE', cache):
            pins = vpn.endpoint_pins()
        self.assertEqual(set(pins), {'jp', 'kr'})

    def test_write_endpoint_pin_and_render_from_cache(self):
        cache = self.root / 'endpoint-cache.json'
        with mock.patch.object(vpn, 'ENDPOINT_CACHE', cache):
            vpn.write_endpoint_pin('jp', '93.184.216.34')
            selected = vpn.render_endpoint_ip('jp', 'vpn.example.com')
            self.assertEqual(selected, '93.184.216.34')

    def test_empty_endpoint_cache_lists_are_unconfigured_not_invalid(self):
        cache = self.root / 'endpoint-cache.json'
        cache.write_text('{"jp": [], "kr": []}')
        cache.chmod(0o600)
        with mock.patch.object(vpn, 'ENDPOINT_CACHE', cache):
            self.assertEqual(vpn.endpoint_pins(), {})
            status = vpn.preflight(VPN_IMAGE)
        self.assertEqual(status['endpoint_cache'], 'OK')
        self.assertEqual(status['endpoint_pin_jp'], 'NOT_CONFIGURED')

    def test_preflight_reports_missing_local_image(self):
        with mock.patch.object(vpn, 'docker_access', return_value='OK'), \
             mock.patch.object(vpn, 'run', side_effect=vpn.VPNError('LOCAL_COMMAND_FAILED')):
            status = vpn.preflight(VPN_IMAGE)
        self.assertEqual(status['vpn'], 'LOCAL_PINNED_IMAGE_MISSING')

    def test_preflight_rejects_unpinned_image_reference(self):
        with mock.patch.object(vpn, 'docker_access', return_value='OK'):
            status = vpn.preflight('qmcgaw/gluetun:latest')
        self.assertEqual(status['vpn'], 'IMMUTABLE_IMAGE_REQUIRED')

    def test_hints_survives_docker_inventory(self):
        digest = 'sha256:' + 'a' * 64
        def fake_run(cmd, input=None, timeout=180):
            if 'inspect' in cmd:
                return digest + '\n'
            if 'images' in cmd:
                return 'qmcgaw/gluetun@' + digest + '\n'
            return ''
        with mock.patch.object(vpn, 'docker_access', return_value='OK'), \
             mock.patch.object(vpn, 'run', side_effect=fake_run):
            data = vpn.hints()
        self.assertEqual(data['core_app_image'], digest)
        self.assertEqual(data['suggested_gluetun_image'], 'qmcgaw/gluetun@' + digest)

    def test_existing_network_is_refused_without_container_or_image_changes(self):
        out, manifest = self.bundle()
        calls = []
        def run(cmd):
            calls.append(cmd)
            return manifest['project']+'_default' if 'network' in cmd else ''
        with mock.patch.object(vpn, 'run', side_effect=run):
            with self.assertRaisesRegex(vpn.VPNError, 'NETWORK_EXISTS'):
                vpn.start(out)
        self.assertFalse(any('up' in c or 'stop' in c or 'inspect' in c for c in calls))

    def test_command_error_does_not_reveal_docker_output(self):
        result = types.SimpleNamespace(returncode=1, stdout='secret', stderr='secret')
        with mock.patch.object(vpn.subprocess,'run',return_value=result):
            with self.assertRaises(vpn.VPNError) as error: vpn.run(['docker'])
        self.assertNotIn('secret', str(error.exception))
