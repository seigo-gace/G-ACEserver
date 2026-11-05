"""Local wiring never grants Host authority or overwrites existing user settings."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gserver_workspace as ws


class WorkspaceIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / 'server-core'
        self.projects = self.root / 'Project'
        self.projects.mkdir()
        self.core.mkdir()
        self.workspace = self.root / 'workspace/G-ACE.code-workspace'
        for name, content in {
            'README.md': 'entry', 'docs/LOAD_SCOPE.md': 'bounded loading',
            'operations/github-project-bounded-host.json': '{}',
            'operations/github-project-rule-plane.json': json.dumps({'rule_planes': {
                'server_ai': {'issue_number': 16}, 'gpt_chat': {'server_ai_default_load': False}}}),
            'scripts/workspace_command_center_check.py':
                'def expected_workspace(core, projects):\n return {"folders": [{"name":"server-core","path":str(core)},{"name":"projects","path":str(projects)}],"settings":{"files.exclude":{"**/.git":True}}}\n',
        }.items():
            p = self.core / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        for args in (['init', '-q'], ['remote', 'add', 'origin', 'git@github.com:G-ACE-inc/server-core.git'],
                     ['add', '.'], ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', '-C', str(self.core), *args], check=True, capture_output=True)

    def files(self):
        return ws.artifacts(self.core, self.projects, self.workspace)

    def test_real_git_identity_and_install_are_offline_and_idempotent(self):
        sha = ws.source(self.core)
        self.assertEqual(len(sha), 40)
        files = self.files()
        ws.install(files)
        before = {p: p.stat().st_mtime_ns for p in files}
        ws.install(files)
        self.assertTrue(ws.verify(files))
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in files})
        folders = json.loads(self.workspace.read_text())['folders']
        self.assertEqual(folders[0]['path'], str(self.core))
        self.assertEqual(folders[1]['path'], str(self.projects))

    def test_wrong_upstream_refused_before_files_are_created(self):
        subprocess.run(['git', '-C', str(self.core), 'remote', 'set-url', 'origin', 'https://github.com/other/server-core'], check=True)
        with self.assertRaisesRegex(ws.WorkspaceError, 'SERVERCORE_ORIGIN_MISMATCH'):
            ws.source(self.core)
        self.assertFalse(self.workspace.exists())

    def test_modified_shared_helper_is_not_executed(self):
        (self.core / 'scripts/workspace_command_center_check.py').write_text('raise RuntimeError("must not execute")')
        with self.assertRaisesRegex(ws.WorkspaceError, 'SERVERCORE_TRACKED_SOURCE_DIRTY'):
            ws.source(self.core)

    def test_existing_user_file_conflict_changes_nothing(self):
        (self.projects / 'AGENTS.md').write_text('user rules and model preferences')
        with self.assertRaisesRegex(ws.WorkspaceError, 'EXISTING_WORKSPACE_FILE_CONFLICT'):
            ws.install(self.files())
        self.assertFalse(self.workspace.exists())
        self.assertEqual((self.projects / 'AGENTS.md').read_text(), 'user rules and model preferences')

    def test_alias_into_another_project_is_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.projects, target_is_directory=True)
        with self.assertRaisesRegex(ws.WorkspaceError, 'WORKSPACE_PATH_ALIAS_REJECTED'):
            ws.artifacts(self.core, alias, self.workspace)

    def test_shared_and_project_roots_may_not_overlap(self):
        with self.assertRaisesRegex(ws.WorkspaceError, 'WORKSPACE_ROOTS_MUST_BE_DISTINCT'):
            ws.artifacts(self.core, self.root, self.workspace)

    def test_partial_install_failure_rolls_back_only_new_files(self):
        files = self.files()
        opened = os.open
        count = 0
        def failing(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('simulated disk failure')
            return opened(*args, **kwargs)
        with mock.patch.object(ws.os, 'open', side_effect=failing), self.assertRaises(OSError):
            ws.install(files)
        self.assertFalse(any(p.exists() for p in files))

    def test_concurrent_replacement_is_preserved_on_failure(self):
        files = self.files()
        def replace_and_fail(fd):
            first = next(iter(files))
            first.unlink()
            first.write_text('concurrent user replacement')
            raise OSError('simulated interruption')
        with mock.patch.object(ws.os, 'fsync', side_effect=replace_and_fail), self.assertRaises(OSError):
            ws.install(files)
        self.assertEqual(next(iter(files)).read_text(), 'concurrent user replacement')

    def test_unchanged_files_survive_later_failure(self):
        files = self.files()
        self.workspace.parent.mkdir()
        self.workspace.write_text(files[self.workspace])
        with mock.patch.object(ws.os, 'open', side_effect=OSError('disk failure')), self.assertRaises(OSError):
            ws.install(files)
        self.assertTrue(self.workspace.exists())

    def test_layout_pass_never_claims_native_rules_or_remote_admission(self):
        args = ['--server-core', str(self.core), '--projects', str(self.projects),
                '--workspace', str(self.workspace), '--install']
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ws.main(args), 0)
        self.assertIn('CLIENT_RULE_LOADING=NOT_VERIFIED', output.getvalue())
        self.assertIn('GSERVER_REMOTE_TERMINAL=NOT_VERIFIED', output.getvalue())
        self.assertNotIn('TERMINAL=PASS', output.getvalue())
        self.assertEqual({p.name for p in (self.projects / '.cursor/rules').iterdir()}, {'00_gace_workspace.mdc'})
