import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / 'scripts/gserver_project_terminal.py'
spec = importlib.util.spec_from_file_location('gserver_project_terminal', MODULE)
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)


class ProjectTerminalTests(unittest.TestCase):
    def test_workspace_registered_repository_executes_in_its_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            projects = Path(root) / 'projects'
            projects.mkdir()
            checkout = Path(root) / 'checkout'
            checkout.mkdir()
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'remote', 'add', 'origin', 'https://github.com/example/repo.git'], check=True)
            sha = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
            workspace = Path(root) / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(checkout)}]}))
            self.assertEqual(terminal.checkout('example/repo', sha, workspace, projects, admit=lambda _repository: True), checkout)
            self.assertEqual(terminal.find_checkout('example/repo', workspace, projects), checkout)
            with self.assertRaisesRegex(ValueError, 'SHA_MISMATCH'):
                terminal.checkout('example/repo', 'a' * 40, workspace, projects, admit=lambda _repository: True)
            with self.assertRaisesRegex(ValueError, 'IDENTITY_INVALID'):
                terminal.checkout('../invalid', sha, workspace, projects)

    def test_future_checkout_needs_no_workspace_entry(self):
        with tempfile.TemporaryDirectory() as root:
            projects = Path(root) / 'projects'
            checkout = projects / 'owner--future'
            checkout.mkdir(parents=True)
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
            subprocess.run(['git', '-C', str(checkout), 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            subprocess.run(['git', '-C', str(checkout), 'remote', 'add', 'origin',
                            'git@github.com:owner/future.git'], check=True)
            workspace = Path(root) / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(projects)}]}))
            self.assertEqual(terminal.checkout('owner/future', workspace=workspace,
                                               projects=projects, admit=lambda _repository: True), checkout)

    def test_first_use_clones_once_without_replacing_other_project(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            projects = root / 'projects'
            projects.mkdir()
            original = projects / 'keep'
            original.mkdir()
            (original / 'data').write_text('preserve')
            source = root / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', '-C', str(source), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(source), 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            path = terminal.clone_checkout('owner/future', projects, source_url=str(source))
            self.assertEqual(path, projects / 'owner--future')
            self.assertEqual(terminal.head(path), terminal.head(source))
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual((original / 'data').read_text(), 'preserve')
            with self.assertRaisesRegex(ValueError, 'DESTINATION_CONFLICT'):
                terminal.clone_checkout('owner/future', projects, source_url=str(source))

    def test_nested_existing_checkout_is_reused_without_clone(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            projects = root / 'projects'
            nested = projects / 'TGtumbler' / 'GateApp-Bot'
            nested.mkdir(parents=True)
            subprocess.run(['git', 'init', '-q', str(nested)], check=True)
            subprocess.run(['git', '-C', str(nested), 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', '-C', str(nested), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(nested), 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            subprocess.run(['git', '-C', str(nested), 'remote', 'add', 'origin',
                            'https://github.com/seigo-gace/GateApp-Bot.git'], check=True)
            workspace = root / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(projects)}]}))
            with mock.patch.object(terminal, 'clone_checkout', side_effect=AssertionError('unexpected clone')):
                self.assertEqual(terminal.checkout('seigo-gace/GateApp-Bot',
                                                   workspace=workspace, projects=projects,
                                                   admit=lambda _repository: True), nested)
            legacy = projects / '旧project' / 'legacy-copy'
            legacy.mkdir(parents=True)
            subprocess.run(['git', 'init', '-q', str(legacy)], check=True)
            subprocess.run(['git', '-C', str(legacy), 'remote', 'add', 'origin',
                            'git@github.com:seigo-gace/GateApp-Bot.git'], check=True)
            self.assertEqual(terminal.checkout('seigo-gace/GateApp-Bot',
                                               workspace=workspace, projects=projects,
                                               admit=lambda _repository: True), nested)
            duplicate = projects / 'duplicate'
            duplicate.mkdir()
            subprocess.run(['git', 'init', '-q', str(duplicate)], check=True)
            subprocess.run(['git', '-C', str(duplicate), 'remote', 'add', 'origin',
                            'https://github.com/seigo-gace/GateApp-Bot.git'], check=True)
            with self.assertRaisesRegex(ValueError, 'NOT_UNIQUE'):
                terminal.checkout('seigo-gace/GateApp-Bot', workspace=workspace,
                                  projects=projects, admit=lambda _repository: True)

    def test_unregistered_repository_is_not_cloned(self):
        with tempfile.TemporaryDirectory() as root:
            projects = Path(root) / 'projects'
            projects.mkdir()
            keep = projects / 'keep'
            keep.mkdir()
            (keep / 'data').write_text('preserve')
            workspace = Path(root) / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(projects)}]}))
            before = sorted(path.name for path in projects.iterdir())
            with mock.patch.object(terminal, 'clone_checkout', side_effect=AssertionError('unexpected clone')):
                with self.assertRaisesRegex(ValueError, 'PROJECT_NOT_REGISTERED'):
                    terminal.checkout('owner/future', workspace=workspace, projects=projects,
                                      admit=lambda _repository: False)
            self.assertEqual(sorted(path.name for path in projects.iterdir()), before)
            self.assertEqual((keep / 'data').read_text(), 'preserve')




if __name__ == '__main__':
    unittest.main()
