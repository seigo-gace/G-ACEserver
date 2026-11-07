import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/gserver_project_terminal.py'
spec = importlib.util.spec_from_file_location('gserver_project_terminal', MODULE)
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)


class ProjectTerminalTests(unittest.TestCase):
    def test_workspace_registered_repository_executes_in_its_checkout(self):
        with tempfile.TemporaryDirectory() as root:
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
            self.assertEqual(terminal.checkout('example/repo', sha, workspace), checkout)
            self.assertEqual(terminal.main(['--repository', 'example/repo', '--sha', sha,
                                            '--workspace', str(workspace), 'test "$(pwd)" = "' + str(checkout) + '"']), 0)
            with self.assertRaisesRegex(ValueError, 'SHA_MISMATCH'):
                terminal.checkout('example/repo', 'a' * 40, workspace)
            with self.assertRaisesRegex(ValueError, 'SHA_MISMATCH'):
                terminal.checkout('example/other', sha, workspace)


if __name__ == '__main__':
    unittest.main()
