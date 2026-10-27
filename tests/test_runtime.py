import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
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

    def request(self, path, auth=None):
        headers = {"Authorization": auth} if auth else {}
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

    def test_ui_and_navigation_available(self):
        self.assertEqual(self.request('/')[0], 200)
        self.assertEqual(self.request('/ui.js')[0], 200)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = ctl.Controller(Path(self.temp.name))
        self.old = 'sha256:' + 'a' * 64
        self.new = 'sha256:' + 'b' * 64

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


if __name__ == '__main__':
    unittest.main()
