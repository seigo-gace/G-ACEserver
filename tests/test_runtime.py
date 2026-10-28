import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
TMP = tempfile.TemporaryDirectory()
os.environ["GSERVER_LOG_DIR"] = TMP.name
spec = importlib.util.spec_from_file_location("gserver", ROOT / "app/gserver.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
spec = importlib.util.spec_from_file_location("ctl", ROOT / "scripts/gserverctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.Server(("127.0.0.1", 0), app.Handler)
        cls.server.start_ts = time.monotonic()
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.credential = Path(TMP.name) / 'credential'
        cls.credential.write_text('x' * 32)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, auth=None, extra_headers=None):
        headers = {"Authorization": auth} if auth else {}
        headers.update(extra_headers or {})
        try:
            response = urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers), timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_liveness_does_not_claim_integration(self):
        code, body = self.request('/health')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), {'status': 'ok', 'service': 'gserver'})

    def test_protected_routes_fail_closed(self):
        for path in ['/status', '/ready', '/storage', '/mounts']:
            self.assertEqual(self.request(path)[0], 401)
        with patch.object(app, 'TOKEN_FILE', str(self.credential)):
            self.assertEqual(self.request('/status', 'Bearer wrong')[0], 401)
            self.assertEqual(self.request('/status', 'Bearer ' + 'x' * 32)[0], 200)

    def test_missing_mount_is_503_not_host_disk(self):
        with patch.object(app, 'TOKEN_FILE', str(self.credential)), patch.object(app.os.path, 'ismount', return_value=False):
            for path in ['/storage', '/ready']:
                self.assertEqual(self.request(path, 'Bearer ' + 'x' * 32)[0], 503)

    def test_mount_disappears_during_stat(self):
        with patch.object(app, 'TOKEN_FILE', str(self.credential)), patch.object(app.os.path, 'ismount', return_value=True), patch.object(app.shutil, 'disk_usage', side_effect=OSError):
            self.assertEqual(self.request('/storage', 'Bearer ' + 'x' * 32)[0], 503)

    def test_credentials_and_query_not_logged(self):
        self.request('/health?password=private-test-value', 'Bearer private-test-value')
        self.assertNotIn('private-test-value', app.LOG_PATH.read_text())

    def test_rotating_log_bound(self):
        handler = app.logger.handlers[0]
        self.assertEqual(handler.maxBytes, 1048576)
        self.assertEqual(handler.backupCount, 4)

    def test_response_request_id_matches_safe_audit_event(self):
        with urllib.request.urlopen(self.url + '/health?private=not-for-log', timeout=3) as response:
            event_id = response.headers['X-Request-ID']
            self.assertEqual(len(event_id), 32)
            response.read()
        log = app.LOG_PATH.read_text()
        self.assertIn('"event_id":"' + event_id + '"', log)
        self.assertNotIn('not-for-log', log)

    def test_ui_and_navigation_available(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/ui.js')[0], 200)

    def test_file_api_requires_authentication_and_explicit_root(self):
        self.assertEqual(self.request('/files')[0], 401)
        self.assertEqual(self.request('/download?path=sample')[0], 401)
        with patch.object(app, 'TOKEN_FILE', str(self.credential)), patch.object(app, 'FILES', None):
            self.assertEqual(self.request('/files', 'Bearer ' + 'x' * 32)[0], 503)

    def test_file_api_listing_download_range_and_traversal(self):
        root = Path(TMP.name) / 'files'
        root.mkdir(exist_ok=True)
        content = b'0123456789' * 10000
        (root / 'sample').write_bytes(content)
        with patch.object(app, 'TOKEN_FILE', str(self.credential)), patch.object(app, 'FILES', app.Storage(TMP.name, str(root))), patch('storage.os.path.ismount', return_value=True):
            auth = 'Bearer ' + 'x' * 32
            code, body = self.request('/files', auth)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)['entries'][0]['name'], 'sample')
            self.assertEqual(self.request('/download?path=sample', auth), (200, content))
            self.assertEqual(self.request('/download?path=sample', auth, {'Range': 'bytes=3-5'}), (206, b'345'))
            self.assertEqual(self.request('/download?path=sample', auth, {'Range': 'bytes=100000-'} )[0], 416)
            self.assertEqual(self.request('/download?path=../credential', auth)[0], 400)
            self.assertEqual(self.request('/files?path=a&path=b', auth)[0], 400)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = ctl.Controller(Path(self.temp.name))
        self.old = 'sha256:' + 'a' * 64
        self.new = 'sha256:' + 'b' * 64
        self.controller.bundle(self.old, create=True)
        self.controller.bundle(self.new, create=True)

    def test_update_and_rollback_persist_immutable_versions(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run'):
            self.controller.activate(self.new)
            self.assertEqual(self.controller.load(), {'current': self.new, 'previous': self.old})
            self.controller.action('rollback')
            self.assertEqual(self.controller.load(), {'current': self.old, 'previous': self.new})

    def test_failure_restores_old_release_without_advancing_record(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run'), patch.object(self.controller, 'compose', side_effect=[subprocess.CalledProcessError(1, 'up'), None]) as compose:
            with self.assertRaises(subprocess.CalledProcessError):
                self.controller.activate(self.new)
            self.assertEqual(compose.call_args_list[1].args[0], self.old)
            self.assertEqual(self.controller.load(), {'current': self.old})

    def test_refuses_existing_unowned_project(self):
        with patch.object(self.controller, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='existing')):
            with self.assertRaises(ValueError):
                self.controller.activate(self.new)
        self.assertFalse(self.controller.record.exists())

    def test_mutable_tags_rejected_without_docker(self):
        with patch.object(self.controller, 'run') as run:
            with self.assertRaises(ValueError):
                self.controller.activate('gserver:latest')
            run.assert_not_called()

    def test_stop_preserves_volumes(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'compose') as compose:
            self.controller.action('stop')
            self.assertEqual(compose.call_args.args[1], ['stop', '--timeout', '10'])

    def test_interrupted_update_requires_recovery_to_committed_release(self):
        self.controller.save({'current': self.old})
        self.controller.write_atomic(self.controller.pending, {'target': self.new})
        with self.assertRaises(ValueError):
            self.controller.activate(self.new)
        with patch.object(self.controller, 'compose') as compose:
            self.controller.action('recover')
            self.assertEqual(compose.call_args.args[0], self.old)
        self.assertFalse(self.controller.pending.exists())

    def test_failed_recovery_retains_journal(self):
        self.controller.save({'current': self.old})
        self.controller.write_atomic(self.controller.pending, {'target': self.new})
        with patch.object(self.controller, 'compose', side_effect=subprocess.CalledProcessError(1, 'up')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.controller.action('recover')
        self.assertTrue(self.controller.pending.exists())

    def test_record_write_failure_keeps_recovery_journal(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run'), patch.object(self.controller, 'save', side_effect=OSError):
            with self.assertRaises(OSError):
                self.controller.activate(self.new)
        self.assertTrue(self.controller.pending.exists())
        self.assertEqual(self.controller.load(), {'current': self.old})

    def test_saved_deployment_survives_source_change(self):
        snapshot = self.controller.bundle(self.old)
        original = snapshot.read_bytes()
        with patch.object(ctl, 'ROOT', Path('/does-not-exist')):
            self.controller.save({'current': self.old})
            with patch.object(self.controller, 'run') as run:
                self.controller.action('start')
                self.assertIn(str(snapshot), run.call_args.args[0])
            self.assertEqual(self.controller.bundle(self.old, create=True).read_bytes(), original)

    def test_snapshot_does_not_depend_on_sudo_environment(self):
        source = self.controller.bundle(self.old).read_text()
        self.assertIn(self.old, source)
        self.assertNotIn('${', source)
        self.assertIn('unix:///var/run/docker.sock', self.controller.docker)

    def test_changed_snapshot_refused_before_docker(self):
        self.controller.bundle(self.old).write_text('tampered')
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run') as run:
            with self.assertRaises(ValueError):
                self.controller.action('start')
            run.assert_not_called()

    def test_loopback_profile_keeps_isolated_snapshot_and_limits_host_port(self):
        source = self.controller.bundle(self.old, create=True, access='loopback').read_text()
        self.assertIn('127.0.0.1:18765:8765', source)
        self.assertIn('internal: true', source)
        self.assertNotIn('network_mode: none', source)
        self.assertIn('network_mode: none', self.controller.bundle(self.old).read_text())

    def test_local_enable_disable_reuses_image_and_volume(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run'):
            self.controller.action('enable-local')
            self.assertEqual(self.controller.load(), {'current': self.old, 'access': 'loopback'})
            self.controller.action('start')
            self.controller.action('disable-local')
            self.assertEqual(self.controller.load(), {'current': self.old})

    def test_local_failure_recovers_original_profile(self):
        self.controller.save({'current': self.old})
        with patch.object(self.controller, 'run'), patch.object(self.controller, 'compose',
            side_effect=[subprocess.CalledProcessError(1, 'up'), None]) as compose:
            with self.assertRaises(subprocess.CalledProcessError):
                self.controller.action('enable-local')
        self.assertEqual(compose.call_args_list[1].args[2], 'isolated')
        self.assertEqual(self.controller.load(), {'current': self.old})

    def test_loopback_profile_survives_image_update(self):
        self.controller.save({'current': self.old, 'access': 'loopback'})
        self.controller.bundle(self.old, create=True, access='loopback')
        with patch.object(self.controller, 'run'):
            self.controller.activate(self.new)
        self.assertEqual(self.controller.load(),
            {'current': self.new, 'previous': self.old, 'access': 'loopback'})

    def test_malformed_release_record_fails_closed(self):
        for data in ([], {'current': None}, {'previous': 42}):
            self.controller.save(data)
            with self.assertRaises(ValueError):
                self.controller.load()


if __name__ == '__main__':
    unittest.main()
