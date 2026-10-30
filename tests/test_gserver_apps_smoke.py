"""Verify destructive probe cleanup is confined to newly guarded app projects."""
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
    spec = importlib.util.spec_from_file_location('app_smoke', SCRIPTS / 'smoke_gserver_apps_host.py')
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)


class SmokeTests(unittest.TestCase):
    def run_probe(self, docker, run, inventory=None):
        output = io.StringIO()
        with mock.patch.object(smoke.apps.os, 'geteuid', return_value=0), \
             mock.patch.object(smoke, 'docker', side_effect=docker), \
             mock.patch.object(smoke.apps, 'run', side_effect=run), \
             mock.patch.object(smoke, 'storage', return_value=['a'*64, 'b'*64]), \
             mock.patch.object(smoke, 'inventory', side_effect=inventory or [{}, {}]), \
             contextlib.redirect_stdout(output):
            result = smoke.main()
        return result, output.getvalue()

    def test_existing_project_is_never_removed(self):
        commands = []
        def docker(*args):
            if args[:1] == ('inspect',):
                return json.dumps([{'State': {'Health': {'Status': 'healthy'}}, 'Image': 'sha256:'+'1'*64}])
            return 'existing-resource'
        def run(cmd, **kwargs):
            commands.append(cmd)
            return ''
        code, output = self.run_probe(docker, run)
        self.assertEqual(code, 1)
        self.assertIn('APP_SMOKE_PROJECT_GUARD', output)
        self.assertEqual(commands, [])

    def test_failed_start_cleans_only_new_disposable_project(self):
        cleanup = []
        def docker(*args):
            if args[:1] == ('inspect',):
                return json.dumps([{'State': {'Health': {'Status': 'healthy'}}, 'Image': 'sha256:'+'1'*64}])
            return ''
        def run(cmd, **kwargs):
            if 'config' in cmd:
                return json.dumps({'services': {'probe': {'image': 'local'}}})
            if 'up' in cmd:
                raise smoke.apps.AppError('DOCKER_COMMAND_FAILED')
            cleanup.append(cmd)
            return ''
        code, output = self.run_probe(docker, run)
        self.assertEqual(code, 1)
        self.assertIn('APP_SMOKE_APP_START', output)
        self.assertEqual(len(cleanup), 1)
        cmd = cleanup[0]
        self.assertIn('down', cmd)
        self.assertIn('--volumes', cmd)
        project = cmd[cmd.index('--project-name')+1]
        self.assertRegex(project, r'^gace-app-probe-[a-f0-9]{16}$')
        self.assertNotIn('gace-gserver', cmd)

    def test_other_container_change_is_failure_even_when_start_failed(self):
        def docker(*args):
            if args[:1] == ('inspect',):
                raise smoke.apps.AppError('DOCKER_COMMAND_FAILED')
            return ''
        code, output = self.run_probe(docker, lambda *a, **kw: '', inventory=[{'original': {}}, {'changed': {}}])
        self.assertEqual(code, 1)
        self.assertIn('APP_SMOKE_CORE_STORAGE_READBACK', output)

    def test_storage_credentials_do_not_leave_container(self):
        with mock.patch.object(smoke, 'docker', return_value=json.dumps(['a'*64, 'b'*64])) as docker:
            self.assertEqual(smoke.storage(), ['a'*64, 'b'*64])
        args = docker.call_args.args
        self.assertEqual(args[:2], ('exec', smoke.CORE))
        self.assertIn("os.environ['GSERVER_AUTH_FILE']", args[-1])
