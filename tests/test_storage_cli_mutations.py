"""End-to-end CLI test in a disposable mount, no network or original files."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
spec = importlib.util.spec_from_file_location('gserver_files_test', ROOT / 'scripts/gserver_files.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CliMutations(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.drive = Path(tmp.name) / 'mnt'
        self.files = self.drive / 'GserverStorage' / 'files'
        self.files.mkdir(parents=True)
        self.incoming = Path(tmp.name) / 'upload'
        self.incoming.mkdir()
        old_drive, old_files = cli.DRIVE, cli.FILES
        cli.DRIVE, cli.FILES = self.drive, self.files
        self.addCleanup(lambda: (setattr(cli, 'DRIVE', old_drive), setattr(cli, 'FILES', old_files)))
        m = patch('os.path.ismount', return_value=True)
        m.start()
        self.addCleanup(m.stop)

    def action(self, *args):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['gserver_files.py', *args]), contextlib.redirect_stdout(output):
            cli.main()
        return json.loads(output.getvalue())

    def test_put_hash_quota_trash_restore_replace(self):
        source = self.incoming / 'a.bin'
        source.write_bytes(b'hello' * 100)
        original = self.action('put', str(source))
        self.assertEqual(original['bytes'], 500)
        self.assertGreater(self.action('quota')['available_bytes'], 0)
        self.assertEqual(self.action('hash', 'a.bin')['sha256'], original['sha256'])
        newer = self.incoming / 'new.bin'
        newer.write_bytes(b'updated')
        changed = self.action('replace', str(newer), 'a.bin', '--expect-sha256', original['sha256'])
        self.assertEqual((self.files / 'a.bin').read_bytes(), b'updated')
        self.assertEqual(len(self.action('trash-list')['entries']), 1)
        old = self.action('trash-info', changed['old_version_id'])
        self.assertEqual(old['sha256'], original['sha256'])
        deleted = self.action('trash', 'a.bin', '--expect-sha256', changed['sha256'])
        self.assertFalse((self.files / 'a.bin').exists())
        self.assertEqual(self.action('list')['entries'], [])
        restored = self.action('restore', deleted['restore_id'], 'a.bin', '--expect-sha256', changed['sha256'])
        self.assertEqual(restored['sha256'], changed['sha256'])
        self.assertEqual((self.files / 'a.bin').read_bytes(), b'updated')

    def test_put_refuses_budget_and_overwrite(self):
        source = self.incoming / 'b.bin'
        source.write_bytes(b'abc')
        with self.assertRaises(ValueError):
            self.action('put', str(source), '--max-bytes', '1')
        self.assertFalse((self.files / 'b.bin').exists())
        self.action('put', str(source))
        with self.assertRaises(FileExistsError):
            self.action('put', str(source))
        self.assertEqual((self.files / 'b.bin').read_bytes(), b'abc')
        self.assertFalse(any(p.name.startswith('.gserver-part-') for p in self.files.iterdir()))


    def test_purge_requires_cli_confirmation_and_matching_hash(self):
        source = self.incoming / 'only.txt'
        source.write_bytes(b'only test data')
        saved = self.action('put', str(source))
        trash = self.action('trash', 'only.txt', '--expect-sha256', saved['sha256'])
        with self.assertRaises(ValueError):
            self.action('purge', trash['restore_id'], '--expect-sha256', saved['sha256'])
        with self.assertRaises(ValueError):
            self.action('purge', trash['restore_id'], '--expect-sha256', '0' * 64, '--confirm-permanent')
        self.action('purge', trash['restore_id'], '--expect-sha256', saved['sha256'], '--confirm-permanent')
        self.assertEqual(self.action('trash-list')['entries'], [])



if __name__ == '__main__':
    unittest.main()
