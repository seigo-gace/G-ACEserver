import contextlib
import importlib.util
import io
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
            self.assertEqual(terminal.checkout('example/repo', sha, workspace, projects,
                                               admit=lambda _repository: True), checkout)
            self.assertEqual(terminal.find_checkout('example/repo', workspace, projects), checkout)
            with self.assertRaisesRegex(ValueError, 'SHA_MISMATCH'):
                terminal.checkout('example/repo', 'a' * 40, workspace, projects,
                                  admit=lambda _repository: True)
            with self.assertRaisesRegex(ValueError, 'IDENTITY_INVALID'):
                terminal.checkout('../invalid', sha, workspace, projects,
                                  admit=lambda _repository: True)

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

    def test_unregistered_repository_is_denied_without_creating_one(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            projects = root / 'projects'
            projects.mkdir()
            original = projects / 'keep'
            original.mkdir()
            (original / 'data').write_text('preserve')
            workspace = root / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(projects)}]}))
            before = sorted(path.name for path in projects.iterdir())
            with self.assertRaisesRegex(ValueError, 'PROJECT_NOT_REGISTERED'):
                terminal.checkout('owner/future', workspace=workspace, projects=projects,
                                  admit=lambda _repository: False)
            self.assertEqual(sorted(path.name for path in projects.iterdir()), before)
            self.assertEqual((original / 'data').read_text(), 'preserve')

    def test_registered_missing_checkout_is_cloned_once(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            projects = root / 'projects'
            projects.mkdir()
            bare = root / 'source.git'
            source = root / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', '-b', 'main', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', '-C', str(source), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(source), 'commit', '--allow-empty', '-qm', 'initial'], check=True)
            subprocess.run(['git', 'clone', '--bare', '-q', str(source), str(bare)], check=True)
            workspace = root / 'workspace.code-workspace'
            workspace.write_text(json.dumps({'folders': [{'path': str(projects)}]}))
            with mock.patch.object(terminal, 'origin_url', lambda _repository: str(bare)):
                first = terminal.checkout('owner/future', workspace=workspace, projects=projects,
                                          admit=lambda _repository: True)
                second = terminal.checkout('owner/future', workspace=workspace, projects=projects,
                                           admit=lambda _repository: True)
            self.assertEqual(first, projects / 'owner--future')
            self.assertEqual(second, first)
            self.assertEqual(terminal.head(first), terminal.head(source))

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

    def test_failed_inner_command_reports_exit_code(self):
        with tempfile.TemporaryDirectory() as root:
            output = io.StringIO()
            with (mock.patch.object(terminal, 'checkout', return_value=Path(root)),
                  mock.patch.object(terminal, 'head', return_value='a' * 40),
                  contextlib.redirect_stderr(output)):
                code = terminal.main(['--repository', 'example/repo', 'exit 42'])
            self.assertEqual(code, 42)
            self.assertIn('PROJECT_TERMINAL_COMMAND_EXIT_CODE=42', output.getvalue())


if __name__ == '__main__':
    unittest.main()
