"""Deterministic audit tests: no actual Docker, credential or network access."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('cf_audit', SCRIPTS / 'audit_gserver_cloudflared_host.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
IMAGE = 'cloudflare/cloudflared@sha256:' + '3' * 64


class LocalCloudflaredAudit(unittest.TestCase):
    def exercise(self, *, help_text='--token-file PATH', entrypoint=None, fail=False, leftover=False):
        calls = []
        def docker(*args):
            calls.append(args)
            if args[:2] == ('image', 'inspect'):
                return json.dumps([{'Config': {'Entrypoint': entrypoint or ['cloudflared']}}])
            if args[0] == 'run':
                if fail:
                    raise audit.apps.AppError('DOCKER_COMMAND_FAILED', diagnostic='synthetic-token-must-not-print')
                return 'cloudflared version 2026.10.0' if args[-1] == 'version' else (help_text if args[-1]=='--help' else 'TOKEN_FILE_READABLE')
            if args[0] == 'compose' and 'up' in args:
                self.fixture_config=json.loads(Path(args[args.index('-f')+1]).read_text())
                return 'probe | TOKEN_FILE_READABLE'
            if args[0] == 'ps': return 'owned-audit-id' if leftover else ''
            return ''
        with mock.patch.object(audit, 'docker', side_effect=docker), \
             mock.patch.object(audit, 'inventory', return_value={'core': 'same'}), \
             mock.patch.object(audit.vpn, 'hints', return_value={'suggested_cloudflared_image': IMAGE,'core_app_image':'sha256:'+'4'*64}), \
             mock.patch.object(audit.vpn,'stage_tunnel_credential'), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = audit.main()
        return result, output.getvalue(), calls

    def test_native_probe_is_offline_nonroot_bounded_and_no_pull(self):
        code, output, calls = self.exercise()
        self.assertEqual(code, 0)
        for call in (c for c in calls if c[0] == 'run'):
            for flag in ('--read-only', '--cap-drop', '--security-opt', '--pids-limit', '--memory', '--cpus'):
                self.assertIn(flag, call)
            self.assertEqual(call[call.index('--network') + 1], 'none')
            self.assertEqual(call[call.index('--pull') + 1], 'never')
            self.assertEqual(call[call.index('--user') + 1], '65534:65534')
            self.assertFalse(any(arg in call for arg in ('--env', '--volume', '--token')))
        service=self.fixture_config['services']['probe']
        self.assertEqual(service['network_mode'],'none')
        self.assertEqual(service['user'],'65534:65534')
        self.assertIn('secrets',service)
        self.assertEqual(len([c for c in calls if c[0]=='compose' and 'down' in c]),1)
        self.assertIn('NATIVE_TOKEN_FILE_SUPPORTED=PASS', output)
        self.assertIn('ACCEPTANCE_CLOUDFLARE=NOT_RUN', output)

    def test_missing_native_file_support_never_passes(self):
        code, output, _ = self.exercise(help_text='other help')
        self.assertEqual(code, 1)
        self.assertIn('CLOUDFLARED_TOKEN_FILE_UNAVAILABLE', output)

    def test_unknown_entrypoint_is_not_executed(self):
        code, output, calls = self.exercise(entrypoint=['unknown-entrypoint'])
        self.assertEqual(code, 1)
        self.assertFalse(any(c[0] == 'run' for c in calls))

    def test_failure_cleans_only_owned_random_label_without_raw_diagnostic(self):
        code, output, calls = self.exercise(fail=True, leftover=True)
        self.assertEqual(code, 1)
        self.assertNotIn('synthetic-token', output)
        self.assertIn(('rm', '-f', 'owned-audit-id'), calls)
        query = next(c for c in calls if c[0] == 'ps')
        self.assertTrue(query[-1].startswith('label=com.gace.gserver.cloudflared-audit='))
        self.assertIn('EXISTING_CONTAINERS_UNCHANGED=PASS', output)
