"""Domain changes must preserve other apps, authorization and recoverable intent."""
import copy
import fcntl
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gserver_domains as d


def policy():
    return {'schema': d.SCHEMA, 'projects': {
        'videobot': {'repository': 'owner/create-videobot', 'zones': ['example.com', 'example.net'],
            'endpoints': {'webhook': {'origin': 'http://127.0.0.1:8080',
                'tunnel': '00000000-0000-0000-0000-000000000001',
                'callbacks': ['/telegram/webhook'], 'application_auth': 'telegram-webhook-secret'}}},
        'tumblr': {'repository': 'owner/tumblr-integration', 'zones': ['example.com'],
            'endpoints': {'web': {'origin': 'http://127.0.0.1:8081',
                'tunnel': '00000000-0000-0000-0000-000000000002', 'callbacks': ['/oauth/callback'],
                'access': {'team_name': 'example-team', 'aud_tags': ['a' * 64]}}}},
    }}


def routes():
    return [{'project': 'videobot', 'endpoint': 'webhook', 'hostname': 'video.example.com'},
            {'project': 'tumblr', 'endpoint': 'web', 'hostname': 'tumblr.example.com'}]


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = d.Store(self.root / 'state')
        self.policy = policy()

    def test_render_preserves_access_callbacks_and_default_denial(self):
        config = d.compile_bindings(self.policy, routes())
        for ingress in config['tunnels'].values():
            self.assertEqual(ingress[-1], {'service': 'http_status:404'})
        ingress = config['tunnels']['00000000-0000-0000-0000-000000000002']
        self.assertEqual(ingress[0]['originRequest']['access'],
                         {'required': True, 'teamName': 'example-team', 'audTag': ['a' * 64]})
        self.assertEqual(config['callbacks'][1]['urls'], ['https://video.example.com/telegram/webhook'])

    def test_new_project_needs_only_configuration(self):
        config = copy.deepcopy(self.policy)
        config['projects']['another-app'] = copy.deepcopy(config['projects']['videobot'])
        config['projects']['another-app']['repository'] = 'owner/another-app'
        config['projects']['another-app']['endpoints']['webhook']['tunnel'] = '00000000-0000-0000-0000-000000000003'
        bindings = routes() + [{'project': 'another-app', 'endpoint': 'webhook', 'hostname': 'other.example.com'}]
        self.assertEqual(len(d.compile_bindings(config, bindings)['bindings']), 3)

    def test_switch_keeps_old_host_other_project_and_auth(self):
        first = self.store.prepare(self.policy, routes(), None)
        before = self.store.load(first)
        second = self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first)
        after = self.store.load(second)
        self.assertEqual(after['bindings'][0], before['bindings'][0])  # sorted: tumblr first
        binding = after['bindings'][1]
        self.assertEqual(binding['hostname'], 'new.example.net')
        self.assertEqual(binding['aliases'], ['video.example.com'])
        self.assertEqual(after['previous'], first)
        self.assertEqual(self.store.load(first), before)
        self.assertEqual(after['callbacks'][1]['auth_contract'], before['callbacks'][1]['auth_contract'])
        self.assertEqual(after['callbacks'][1]['urls'], ['https://new.example.net/telegram/webhook'])

    def test_drop_alias_and_rollback_are_explicit_and_versioned(self):
        first = self.store.prepare(self.policy, routes(), None)
        second = self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first)
        third = self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', second, keep_old=False)
        self.assertEqual(self.store.load(third)['bindings'][1]['aliases'], [])
        fourth = self.store.rollback(self.policy, first, third)
        self.assertEqual(self.store.load(fourth)['bindings'], self.store.load(first)['bindings'])
        self.assertEqual(self.store.current(), fourth)

    def test_stale_revision_cannot_overwrite_another_change(self):
        first = self.store.prepare(self.policy, routes(), None)
        second = self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first)
        with self.assertRaisesRegex(d.DomainError, 'REVISION_CONFLICT'):
            self.store.switch(self.policy, 'tumblr', 'web', 'other.example.com', first)
        self.assertEqual(self.store.current(), second)

    def test_collision_including_alias_and_case_is_rejected(self):
        for extra in ({'hostname': 'VIDEO.EXAMPLE.COM'}, {'aliases': ['video.example.com']}):
            bindings = routes()
            bindings[1].update(extra)
            with self.subTest(extra=extra), self.assertRaisesRegex(d.DomainError, 'HOSTNAME_CONFLICT'):
                d.compile_bindings(self.policy, bindings)

    def test_wrong_zone_wildcard_ip_and_suffix_tricks_are_rejected(self):
        for host in ('evil.com', 'video.example.com.evil.net', 'badexample.com', '*.example.com', '127.0.0.1', 'a_b.example.com'):
            bindings = routes()
            bindings[0]['hostname'] = host
            with self.subTest(host=host), self.assertRaises(d.DomainError):
                d.compile_bindings(self.policy, bindings)

    def test_callback_paths_and_public_or_secret_origins_are_rejected(self):
        for value in ('https://public.example.com:443', 'http://169.254.169.254:80',
                      'http://user:password@app:80', 'http://@app:80', 'http://app:80/?secret=1',
                      'http://app:80/path', 'http://app:\n80', 'ssh://app:22'):
            with self.subTest(origin=value), self.assertRaises(d.DomainError):
                d.origin(value)
        self.assertEqual(d.origin('http://[::1]:8080/'), 'http://[::1]:8080')
        changed = copy.deepcopy(self.policy)
        changed['projects']['videobot']['endpoints']['webhook']['callbacks'] = ['/../admin']
        with self.assertRaisesRegex(d.DomainError, 'INVALID_CALLBACK_PATH'):
            d.compile_bindings(changed, routes())

    def test_unknown_secret_fields_and_missing_auth_are_rejected(self):
        for change in ('token', 'missing'):
            config = copy.deepcopy(self.policy)
            endpoint = config['projects']['videobot']['endpoints']['webhook']
            if change == 'token':
                endpoint['token'] = 'never-store-credentials-here'
            else:
                endpoint.pop('application_auth')
            with self.subTest(change=change), self.assertRaises(d.DomainError):
                d.compile_bindings(config, routes())

    def test_cross_project_origin_ownership_is_explicit(self):
        config = copy.deepcopy(self.policy)
        source = config['projects']['videobot']['endpoints']['webhook']
        target = config['projects']['tumblr']['endpoints']['web']
        target.update(origin=source['origin'], tunnel=source['tunnel'])
        with self.assertRaisesRegex(d.DomainError, 'ORIGIN_OWNERSHIP_CONFLICT'):
            d.compile_bindings(config, routes())

    def test_rollback_cannot_restore_a_revoked_zone(self):
        first = self.store.prepare(self.policy, routes(), None)
        second = self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first, keep_old=False)
        changed = copy.deepcopy(self.policy)
        changed['projects']['videobot']['zones'] = ['example.net']
        with self.assertRaisesRegex(d.DomainError, 'ZONE_NOT_ALLOWED'):
            self.store.rollback(changed, first, second)
        self.assertEqual(self.store.current(), second)

    def test_changed_policy_requires_reprepare_before_export(self):
        first = self.store.prepare(self.policy, routes(), None)
        changed = copy.deepcopy(self.policy)
        changed['projects']['tumblr']['endpoints']['web']['access']['aud_tags'] = ['b' * 64]
        with self.assertRaisesRegex(d.DomainError, 'POLICY_CHANGED_REPREPARE'):
            self.store.export(changed, first, self.root / 'export')
        self.assertFalse((self.root / 'export').exists())

    def test_private_json_rejects_exposed_files_links_and_duplicate_keys(self):
        path = self.root / 'policy.json'
        path.write_text('{"schema":1}')
        path.chmod(0o644)
        with self.assertRaisesRegex(d.DomainError, 'PRIVATE_FILE_REQUIRED'):
            d.read_json(path)
        path.chmod(0o600)
        link = self.root / 'link.json'
        link.symlink_to(path)
        with self.assertRaisesRegex(d.DomainError, 'SYMLINK_FORBIDDEN'):
            d.read_json(link)
        path.write_text('{"schema":1,"schema":2}')
        with self.assertRaisesRegex(d.DomainError, 'DUPLICATE_JSON_KEY'):
            d.read_json(path)

    def test_revision_tampering_is_not_exported(self):
        first = self.store.prepare(self.policy, routes(), None)
        file = self.store.revisions / (first + '.json')
        file.write_text('{}')
        with self.assertRaisesRegex(d.DomainError, 'REVISION_CHANGED'):
            self.store.export(self.policy, first, self.root / 'export')

    def test_failed_atomic_replace_preserves_previous_desired_pointer(self):
        first = self.store.prepare(self.policy, routes(), None)
        with patch.object(d.os, 'replace', side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError):
                self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first)
        self.assertEqual(self.store.current(), first)

    def test_concurrent_lock_refuses_writer(self):
        first = self.store.prepare(self.policy, routes(), None)
        fd = os.open(self.store.root / 'operation.lock', os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(d.DomainError, 'STATE_BUSY'):
                self.store.switch(self.policy, 'videobot', 'webhook', 'new.example.net', first)
        finally:
            os.close(fd)
        self.assertEqual(self.store.current(), first)

    def test_export_is_private_fresh_and_never_marks_live_applied(self):
        first = self.store.prepare(self.policy, routes(), None)
        output = self.root / 'export'
        self.store.export(self.policy, first, output)
        plan = d.read_json(output / 'plan.json')
        self.assertEqual(plan['live_status'], 'NOT_VERIFIED')
        self.assertEqual(plan['status'], 'DESIRED_ONLY')
        self.assertIn('callbacks', plan['required_live_readback'])
        before = (output / 'plan.json').read_bytes()
        with self.assertRaisesRegex(d.DomainError, 'FRESH_OUTPUT_REQUIRED'):
            self.store.export(self.policy, first, output)
        self.assertEqual((output / 'plan.json').read_bytes(), before)

    def test_cli_prepare_switch_export_keeps_domains_out_of_stdout(self):
        private_policy = self.root / 'policy.json'
        private_routes = self.root / 'routes.json'
        d.write_new(private_policy, self.policy)
        d.write_new(private_routes, {'schema': d.SCHEMA, 'bindings': routes()})
        def command(action, *args):
            result = subprocess.run([sys.executable, '-B', d.__file__, action,
                '--state', str(self.store.root), *args], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('DOMAIN_LIVE_STATUS=NOT_VERIFIED', result.stdout)
            self.assertNotIn('video.example.com', result.stdout)
            self.assertNotIn('new.example.net', result.stdout)
        command('prepare', '--policy', str(private_policy), '--routes', str(private_routes), '--expect', 'none')
        first = self.store.current()
        command('switch', '--policy', str(private_policy), '--project', 'videobot', '--endpoint', 'webhook',
                '--hostname', 'new.example.net', '--expect', first)
        command('export', '--policy', str(private_policy), '--output', str(self.root / 'cli-export'))
        plan = d.read_json(self.root / 'cli-export/plan.json')
        self.assertEqual(plan['bindings'][1]['aliases'], ['video.example.com'])
        self.assertEqual(plan['bindings'][1]['hostname'], 'new.example.net')

    def test_repeated_identical_configuration_does_not_grow_history(self):
        first = self.store.prepare(self.policy, routes(), None)
        second = self.store.prepare(self.policy, copy.deepcopy(routes()), first)
        third = self.store.switch(self.policy, 'videobot', 'webhook', 'video.example.com', second)
        self.assertEqual((first, second, third), (first, first, first))
        self.assertEqual(len(list(self.store.revisions.glob('*.json'))), 1)
