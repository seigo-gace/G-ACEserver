"""Protect consumer probe ownership, provenance and secret boundaries."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import smoke_videobot_integration as probe


class SourceTests(unittest.TestCase):
    def test_changed_and_symlinked_app_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / 'src/main.mjs'
            file.parent.mkdir()
            content = b'known source'
            file.write_bytes(content)
            blob = hashlib.sha1(b'blob 12\0' + content).hexdigest()
            with patch.object(probe, 'SOURCE_BLOBS', {'src/main.mjs': blob}):
                self.assertEqual(probe.source_directory(root), root)
                file.write_text('modified')
                with self.assertRaisesRegex(probe.ProbeError, 'VERSION_MISMATCH'):
                    probe.source_directory(root)
                file.unlink()
                target = root / 'target'
                target.write_bytes(content)
                file.symlink_to(target)
                with self.assertRaisesRegex(probe.ProbeError, 'SOURCE_SYMLINK'):
                    probe.source_directory(root)

    def test_mutable_image_rejected_before_docker_access(self):
        with patch.object(probe, 'source_directory', return_value=Path('/trusted')), patch.object(probe, 'docker') as docker:
            with self.assertRaisesRegex(probe.ProbeError, 'IMMUTABLE_LOCAL_NODE_IMAGE_REQUIRED'):
                probe.verify('/trusted', 'node:22-alpine')
            docker.assert_not_called()

    def test_local_log_rotation_supports_default_compression(self):
        args = probe.bounded_container('private-test-network')
        self.assertIn('max-file=2', args)
        self.assertNotIn('max-file=1', args)

    def test_errors_do_not_echo_private_diagnostics(self):
        from subprocess import CompletedProcess
        with patch.object(probe.subprocess, 'run', return_value=CompletedProcess([], 1, 'private-token', 'private-key')):
            with self.assertRaisesRegex(probe.ProbeError, '^DOCKER_OPERATION_FAILED_INSPECT$'):
                probe.docker('inspect', 'synthetic')


class LifecycleTests(unittest.TestCase):
    prefix = 'gserver-videobot-probe-' + 'a' * 16
    core = 'c' * 64
    network = 'b' * 64
    token = 'a' * 64

    def run_probe(self, *, fail_client=False, foreign_volume=False, external_network=False, changed_services=False):
        calls, created = [], []
        def docker(*args, input=None):
            calls.append((args, input))
            if args[:2] == ('image', 'inspect'):
                return '[]'
            if args[0] == 'inspect':
                return json.dumps([{'Image': 'sha256:' + 'f' * 64, 'State': {'Health': {'Status': 'healthy'}}}])
            if args[:2] == ('volume', 'ls'):
                return ''
            if args[:2] == ('volume', 'create'):
                return self.prefix
            if args[:2] == ('volume', 'inspect'):
                return json.dumps([{'Labels': {'gserver.acceptance': 'foreign' if foreign_volume else self.prefix}}])
            if args[:2] == ('network', 'create'):
                return self.network
            if args[:2] == ('network', 'inspect'):
                return json.dumps([{'Internal': not external_network}])
            if args[0] == 'create':
                cid = 'cde'[len(created)] * 64
                created.append(cid)
                return cid
            if args[:3] == ('start', '-a', '-i'):
                if fail_client:
                    raise probe.ProbeError('DOCKER_OPERATION_FAILED')
                return 'VIDEOBOT_BOOTSTRAP_ADMISSION_AUTH_REPLAY_CONFLICT=PASS'
            if args[0] == 'exec' and args[-1] == probe.PROVISION:
                return json.dumps({'bot': self.token})
            return ''
        output = io.StringIO()
        error = None
        inventories = [{'production': 'stable'}, {'production': 'changed' if changed_services else 'stable'}]
        with patch.object(probe, 'source_directory', return_value=Path('/trusted')), \
             patch.object(probe, 'docker', side_effect=docker), \
             patch.object(probe.secrets, 'token_hex', return_value='a' * 16), \
             patch.object(probe, 'wait_core'), \
             patch.object(probe, 'receipt', return_value='f' * 64), \
             patch.object(probe, 'inventory', side_effect=inventories), \
             patch.object(probe, 'storage', return_value=['stable']), \
             contextlib.redirect_stdout(output):
            try:
                probe.verify('/trusted', 'sha256:' + '1' * 64)
            except probe.ProbeError as exc:
                error = str(exc)
        return calls, output.getvalue(), error

    def test_success_restarts_only_owned_core_and_keeps_secret_in_stdin(self):
        calls, output, error = self.run_probe()
        self.assertIsNone(error)
        self.assertIn('VERIFY=PASS', output)
        self.assertNotIn(self.token, output)
        self.assertEqual([args for args, _ in calls if args[0] == 'restart'], [('restart', self.core)])
        for args, payload in calls:
            self.assertNotIn(self.token, args)
            if payload:
                self.assertEqual(json.loads(payload), {'token': self.token})
        creates = [args for args, _ in calls if args[0] == 'create']
        self.assertEqual(len(creates), 3)
        for args in creates:
            for required in ('--read-only', '--cap-drop', '--memory', '--pids-limit', '--pull'):
                self.assertIn(required, args)
            self.assertNotIn('--publish', args)
            self.assertNotIn('--privileged', args)
        removed = [args[-1] for args, _ in calls if args[:2] == ('rm', '-f')]
        self.assertEqual(removed, ['e' * 64, 'd' * 64, self.core])

    def test_failed_client_still_cleans_only_owned_resources(self):
        calls, output, error = self.run_probe(fail_client=True)
        self.assertEqual(error, 'DOCKER_OPERATION_FAILED')
        self.assertNotIn('VERIFY=PASS', output)
        self.assertEqual([args[-1] for args, _ in calls if args[:2] == ('rm', '-f')], ['d' * 64, self.core])
        self.assertIn((('network', 'rm', self.network), None), calls)
        self.assertIn((('volume', 'rm', self.prefix), None), calls)

    def test_foreign_volume_is_never_selected_for_cleanup(self):
        calls, _, error = self.run_probe(foreign_volume=True)
        self.assertEqual(error, 'VOLUME_NOT_OWNED')
        self.assertFalse(any(args[:2] == ('volume', 'rm') for args, _ in calls))
        self.assertFalse(any(args[0] == 'create' for args, _ in calls))

    def test_external_network_is_rejected_before_container_start(self):
        calls, _, error = self.run_probe(external_network=True)
        self.assertEqual(error, 'EXTERNAL_NETWORK_FORBIDDEN')
        self.assertFalse(any(args[0] == 'create' for args, _ in calls))

    def test_production_change_prevents_acceptance_after_cleanup(self):
        _, output, error = self.run_probe(changed_services=True)
        self.assertEqual(error, 'EXISTING_SERVICES_CHANGED')
        self.assertNotIn('VERIFY=PASS', output)
