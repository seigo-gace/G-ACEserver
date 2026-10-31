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

    def test_restart_recreates_process_without_volume_removal(self):
        data = {'services': {'web': {'image': 'sha256:' + '0' * 64}}}
        with mock.patch.object(a, 'run', side_effect=[json.dumps(data), '', '']) as run:
            a.execute('restart', self.file, 'web')
            self.assertEqual(len(run.call_args_list), 3)
            restart_cmd = run.call_args_list[1].args[0]
            up_cmd = run.call_args_list[2].args[0]
            self.assertIn('restart', restart_cmd)
            self.assertNotIn('down', restart_cmd)
            self.assertIn('up', up_cmd)
            self.assertIn('--no-build', up_cmd)
            self.assertEqual(up_cmd[up_cmd.index('--pull') + 1], 'never')

    def test_no_secrets_emitted_on_docker_errors(self):
        class Result: returncode=1; stdout='secret'; stderr='password=sensitive'
        with mock.patch.object(a.subprocess, 'run', return_value=Result()):
            with self.assertRaisesRegex(a.AppError, '^DOCKER_COMMAND_FAILED$'):
                a.run(['docker','info'])

    def test_explicit_names_cannot_share_core_or_another_app_resources(self):
        for key in ('networks', 'volumes'):
            for name in ('gace-gserver_state', 'gace-app-other_state'):
                with self.subTest(key=key, name=name), self.assertRaisesRegex(a.AppError, 'CROSS_PROJECT'):
                    self.config({'services': {'web': {}}, key: {'state': {'name': name}}})
            self.config({'services': {'web': {}}, key: {'state': {'name': 'gace-app-sample_state'}}})

    def test_volume_driver_cannot_mount_host_data(self):
        for props in ({'driver': 'nfs'}, {'driver': 'local', 'driver_opts': {'type': 'none', 'device': '/', 'o': 'bind'}}):
            with self.subTest(props=props), self.assertRaisesRegex(a.AppError, 'RESOURCE_DRIVER'):
                self.config({'services': {'web': {}}, 'volumes': {'state': props}})

    def test_bind_paths_confined_to_app_directory(self):
        for path in ('/', '/var/run', '/etc', '/mnt/f', '/mnt/g'):
            with self.subTest(path=path), self.assertRaises(a.AppError):
                self.config({'services': {'web': {'volumes': [{'type': 'bind', 'source': path}]}}})
        link = Path(self.tmp.name) / 'host'
        link.symlink_to('/etc', target_is_directory=True)
        with self.assertRaises(a.AppError):
            self.config({'services': {'web': {'volumes': [{'type': 'bind', 'source': str(link)}]}}})
        self.config({'services': {'web': {'volumes': [{'type': 'bind', 'source': str(self.file)}]}}})

    def test_privileged_hooks_and_provider_are_rejected(self):
        for props in ({'post_start': [{'command': 'x', 'privileged': True}]},
                      {'provider': {'type': 'external'}}, {'use_api_socket': True},
                      {'uts': 'host'}, {'cgroup': 'host'}, {'runtime': 'custom'},
                      {'volumes': [{'type': 'image', 'source': 'registry/image'}]},
                      {'pid': 'service:other'}, {'ipc': 'container:core'},
                      {'deploy': {'resources': {'reservations': {'devices': [{'capabilities': ['gpu']}]}}}}):
            with self.subTest(props=props), self.assertRaises(a.AppError):
                self.config({'services': {'web': props}})

    def test_secret_and_config_cannot_reference_protected_files(self):
        for key in ('secrets', 'configs'):
            with self.subTest(key=key), self.assertRaises(a.AppError):
                self.config({'services': {'web': {}}, key: {'key': {'file': '/etc/passwd'}}})

    def test_execution_uses_validated_snapshot_and_preserves_literal_dollars(self):
        config = {'services': {'web': {'image': 'local', 'environment': {'KEY': '$$PRIVATE'}}}}
        snapshots = []
        def run(cmd, **kwargs):
            if 'config' in cmd:
                return json.dumps(config)
            path = Path(cmd[cmd.index('-f') + 1])
            self.assertNotEqual(path, self.file)
            self.assertEqual(json.loads(path.read_text())['services']['web']['environment']['KEY'], '$$PRIVATE')
            self.assertEqual(cmd[cmd.index('--project-directory') + 1], str(self.file.parent))
            snapshots.append(path)
            return ''
        with mock.patch.object(a, 'run', side_effect=run):
            a.execute('start', self.file, 'sample')
        self.assertTrue(snapshots)
        self.assertFalse(snapshots[0].exists())

    def test_failed_start_removes_secret_snapshot(self):
        snapshots = []
        def run(cmd, **kwargs):
            if 'config' in cmd:
                return json.dumps({'services': {'web': {}}})
            snapshots.append(Path(cmd[cmd.index('-f') + 1]))
            raise a.AppError('DOCKER_COMMAND_FAILED')
        with mock.patch.object(a, 'run', side_effect=run), self.assertRaises(a.AppError):
            a.execute('start', self.file, 'sample')
        self.assertFalse(snapshots[0].exists())

    def test_status_does_not_print_unknown_service_or_untrusted_state(self):
        for row in ({'Service': 'unknown', 'State': 'running'}, {'Service': 'web', 'State': 'secret'}):
            with mock.patch.object(a, 'run', side_effect=[json.dumps({'services': {'web': {}}}), json.dumps(row)]):
                with self.assertRaisesRegex(a.AppError, 'STATUS_FORMAT_INVALID'):
                    a.execute('status', self.file, 'sample')

    def test_local_logging_compression_and_file_count_are_compatible(self):
        for options in ({'max-file': '1'}, {'max-file': '1', 'compress': 'true'}, {'max-file': '0'}, {'max-file': 'invalid'}):
            with self.subTest(options=options), self.assertRaisesRegex(a.AppError, 'LOCAL_LOG_ROTATION_INVALID'):
                self.config({'services': {'web': {'logging': {'driver': 'local', 'options': options}}}})
        for options in ({'max-file': '2'}, {'max-file': '1', 'compress': 'false'}, {}):
            with self.subTest(options=options):
                self.config({'services': {'web': {'logging': {'driver': 'local', 'options': options}}}})

if __name__ == '__main__': unittest.main()
