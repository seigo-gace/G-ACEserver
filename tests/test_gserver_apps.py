import importlib.util
import json
from pathlib import Path
from unittest import mock
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'gserver_apps.py'
spec = importlib.util.spec_from_file_location('gserver_apps', MODULE)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'compose.yaml'
        self.file.write_text('services: {}\n')

    def config(self, data, action='verify', name='sample'):
        with mock.patch.object(a, 'run', return_value=json.dumps(data)) as runner:
            a.execute(action, self.file, name)
            return runner.call_args_list

    def test_names_and_project_isolation(self):
        self.assertEqual(a.project('tumblr'), 'gace-app-tumblr')
        for bad in ('../../x', 'A', '', '-a', 'a'*50):
            with self.assertRaises(a.AppError): a.project(bad)

    def test_file_is_not_symlink(self):
        link = Path(self.tmp.name) / 'link.yaml'
        link.symlink_to(self.file)
        with self.assertRaisesRegex(a.AppError, 'UNSAFE'): a.compose_file(link)

    def test_rejects_public_ports_and_host_privilege(self):
        for props in ({'ports':[{'target':80,'published':'80','host_ip':'0.0.0.0'}]},
                      {'network_mode':'host'}, {'network_mode':'container:gace-gserver-gserver-1'}, {'privileged':True}, {'container_name':'gace-gserver-gserver-1'},
                      {'volumes':[{'type':'bind','source':'/var/run/docker.sock','target':'/sock'}]}):
            with self.subTest(props=props), self.assertRaises(a.AppError):
                self.config({'services':{'web':{'image':'sha256:'+'0'*64, **props}}})

    def test_external_resources_are_rejected(self):
        for config in (
                {"services":{"web":{}},"networks":{"default":{"external":True}}},
                {"services":{"web":{}},"volumes":{"data":{"external":True}}}):
            with self.assertRaisesRegex(a.AppError, "EXTERNAL_RESOURCE_NOT_ALLOWED"):
                self.config(config)

    def test_accepts_local_ports_and_separate_app(self):
        calls = self.config({'services':{'web':{'image':'sha256:'+'0'*64, 'ports':[{'host_ip':'127.0.0.1','target':80,'published':'10080'}]}}})
        self.assertIn('gace-app-sample', calls[0].args[0])
        self.assertIn('/dev/null', calls[0].args[0])
        self.assertIn('unix:///var/run/docker.sock', calls[0].args[0])

    def test_start_uses_existing_local_image_only(self):
        data={'services':{'web':{'image':'sha256:'+'0'*64}}}
        with mock.patch.object(a, 'run', side_effect=[json.dumps(data), '']) as run:
            a.execute('start', self.file, 'web')
            self.assertEqual(len(run.call_args_list), 2)
            cmd=run.call_args_list[-1].args[0]
            self.assertIn('--no-build',cmd)
            self.assertEqual(cmd[cmd.index('--pull')+1], 'never')
            self.assertNotIn('down',cmd)

    def test_stop_never_deletes_state(self):
        with mock.patch.object(a,'run',side_effect=[json.dumps({'services':{'web':{}}}), '']) as run:
            a.execute('stop', self.file, 'web')
            self.assertIn('stop', run.call_args_list[-1].args[0])
            self.assertNotIn('down', run.call_args_list[-1].args[0])

    def test_no_secrets_emitted_on_docker_errors(self):
        class Result: returncode=1; stdout='secret'; stderr='password=sensitive'
        with mock.patch.object(a.subprocess, 'run', return_value=Result()):
            with self.assertRaisesRegex(a.AppError, '^DOCKER_COMMAND_FAILED$'):
                a.run(['docker','info'])

if __name__ == '__main__': unittest.main()
