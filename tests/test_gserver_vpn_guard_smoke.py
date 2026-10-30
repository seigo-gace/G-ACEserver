"""Offline safety/cleanup tests; these are not kernel or VPN acceptance."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
with mock.patch.object(sys, 'path', [str(SCRIPTS)] + sys.path):
    spec = importlib.util.spec_from_file_location('guard_smoke', SCRIPTS / 'smoke_gserver_vpn_guard.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)


class GuardSmokeTests(unittest.TestCase):
    def exercise(self, fail_guard=False, canary_ip='172.18.0.2', packets=1):
        project = ''
        cleanup = []

        def remember_project(args):
            nonlocal project
            for arg in args:
                if arg.startswith('label=com.docker.compose.project='):
                    project = arg.rsplit('=', 1)[1]

        def docker(*args):
            if args[0] == 'ps':
                if '-aq' in args:
                    return ''
                remember_project(args)
                if any('service=canary' in a for a in args):
                    return 'canary-id'
                if any('service=probe' in a for a in args):
                    return 'probe-id'
                return 'probe-id'
            if args[0] == 'network':
                return ''
            if args[:2] == ('inspect', guard.CORE):
                return json.dumps([{'State': {'Health': {'Status': 'healthy'}}, 'Image': 'sha256:' + '1' * 64}])
            if args[:2] == ('inspect', 'canary-id'):
                return json.dumps([{'NetworkSettings': {'Networks': {'own': {'IPAddress': canary_ip}}}}])
            if args[:2] == ('inspect', 'probe-id'):
                return json.dumps([{'State': {'Pid': 1234},
                    'Config': {'Labels': {'com.docker.compose.project': project}}}])
            return ''

        def report(count):
            return {'inode': 3, 'nft': {'nftables': [{'rule': {'expr': [
                {'counter': {'packets': count, 'bytes': count * 40}}, {'drop': None}]}}]}}

        reports = [guard.vpn.VPNError('TEST_GUARD_FAILURE')] if fail_guard else [report(0), report(0), report(packets)]
        output = io.StringIO()
        with mock.patch.object(guard, 'docker', side_effect=docker), \
             mock.patch.object(guard, 'inventory', return_value={}), \
             mock.patch.object(guard, 'storage', return_value=['same']), \
             mock.patch.object(guard.apps, 'execute'), \
             mock.patch.object(guard.apps, 'run', side_effect=lambda c: cleanup.append(c) or ''), \
             mock.patch.object(guard.vpn, 'namespace_guard', side_effect=reports), \
             mock.patch.object(guard, 'connect') as connect, \
             contextlib.redirect_stdout(output):
            code = guard.main()
        return code, output.getvalue(), cleanup, connect

    def test_only_private_canary_and_loopback_are_used(self):
        code, output, cleanup, connect = self.exercise()
        self.assertEqual(code, 0)
        self.assertIn('DROP_COUNTER_INCREASED=PASS', output)
        self.assertIn('WIREGUARD_CONNECTION=NOT_TESTED', output)
        self.assertEqual([c.args[1:] for c in connect.call_args_list],
                         [('172.18.0.2', guard.CANARY_PORT, True),
                          ('127.0.0.1', guard.PORT, True),
                          ('172.18.0.2', guard.CANARY_PORT, False)])
        self.assertEqual(len(cleanup), 1)
        self.assertIn('down', cleanup[0])
        self.assertNotIn('--volumes', cleanup[0])
        self.assertNotIn('gace-gserver', cleanup[0])

    def test_failed_guard_still_cleans_only_new_project(self):
        code, output, cleanup, connect = self.exercise(fail_guard=True)
        self.assertEqual(code, 1)
        self.assertIn('ERROR=NAMESPACE_GUARD_INSTALL_GUARD', output)
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(len(cleanup), 1)

    def test_public_canary_is_refused_before_connection(self):
        code, output, cleanup, connect = self.exercise(canary_ip='8.8.8.8')
        self.assertEqual(code, 1)
        self.assertIn('VERIFY=FAIL', output)
        connect.assert_not_called()
        self.assertEqual(len(cleanup), 1)

    def test_block_without_observed_nft_drop_does_not_pass(self):
        code, output, cleanup, _ = self.exercise(packets=0)
        self.assertEqual(code, 1)
        self.assertIn('ERROR=NAMESPACE_GUARD_CANARY_DENY', output)
        self.assertNotIn('DROP_COUNTER_INCREASED=PASS', output)
        self.assertEqual(len(cleanup), 1)
