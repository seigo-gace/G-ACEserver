"""Recoverable storage mutation tests on a disposable simulated G: mount."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from storage import Storage, InvalidPath
from storage_mutations import digest, quota, to_trash, restore, trash_list, trash_info, replace_version


class Mutations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.drive = Path(self.tmp.name)
        self.root = self.drive / 'allowed'
        self.root.mkdir()
        self.store = Storage(str(self.drive), str(self.root))
        m = patch('storage.os.path.ismount', return_value=True)
        m.start()
        self.addCleanup(m.stop)

    def test_hash_delete_and_restore_with_no_overwrite(self):
        data = os.urandom(1024 * 1024 + 3)
        f = self.root / 'a.bin'
        f.write_bytes(data)
        d = digest(self.store, 'a.bin')
        self.assertEqual(d['sha256'], hashlib.sha256(data).hexdigest())
        receipt = to_trash(self.store, 'a.bin', d['sha256'])
        self.assertFalse(f.exists())
        self.assertEqual(self.store.listing()['entries'], [])
        with self.assertRaises(InvalidPath):
            self.store.listing('.gserver-trash')
        with self.assertRaises(InvalidPath):
            with self.store.open_file('.gserver-trash/' + receipt['restore_id']):
                pass
        f.write_bytes(b'new-value')
        with self.assertRaises(FileExistsError):
            restore(self.store, receipt['restore_id'], 'a.bin', d['sha256'])
        self.assertEqual(f.read_bytes(), b'new-value')
        f.unlink()
        restored = restore(self.store, receipt['restore_id'], 'a.bin', d['sha256'])
        self.assertEqual(restored['bytes'], len(data))
        self.assertEqual(f.read_bytes(), data)

    def test_bad_digest_and_alias_fail_without_loss(self):
        f = self.root / 'live.txt'
        f.write_text('important')
        sha = hashlib.sha256(b'important').hexdigest()
        with self.assertRaises(ValueError):
            to_trash(self.store, 'live.txt', '0' * 64)
        for bad in ('../live.txt', '.gserver-trash', '.GSERVER-TRASH', 'NUL', 'x/y'):
            with self.subTest(bad=bad), self.assertRaises(InvalidPath):
                to_trash(self.store, bad, sha)
        self.assertEqual(f.read_text(), 'important')
        self.assertFalse((self.root / '.gserver-trash').exists())

    def test_symlink_hardlink_blocked_and_quota(self):
        f = self.root / 'live.txt'
        f.write_text('hi')
        (self.root / 'sym').symlink_to(f)
        sha = hashlib.sha256(b'hi').hexdigest()
        with self.assertRaises((InvalidPath, OSError)):
            to_trash(self.store, 'sym', sha)
        (self.root / 'hardlink').hardlink_to(f)
        with self.assertRaises(InvalidPath):
            to_trash(self.store, 'live.txt', sha)
        info = quota(self.store)
        self.assertGreater(info['total_bytes'], info['available_bytes'])
        self.assertGreater(info['block_size'], 0)

    def test_failed_link_preserves_original(self):
        f = self.root / 'important'
        f.write_bytes(b'hello')
        sha = hashlib.sha256(b'hello').hexdigest()
        with patch('storage_mutations.os.link', side_effect=OSError(28, 'disk full')):
            with self.assertRaises(OSError):
                to_trash(self.store, 'important', sha)
        self.assertEqual(f.read_bytes(), b'hello')

    def test_recoverable_atomic_version_change(self):
        old = b'v1' * 131072
        new = b'v2' * 123457
        live = self.root / 'file.bin'
        live.write_bytes(old)
        source = self.drive / 'source.bin'
        source.write_bytes(new)
        sha = hashlib.sha256(old).hexdigest()
        with open(source, 'rb') as handle:
            receipt = replace_version(self.store, 'file.bin', handle.fileno(), sha, reserve_bytes=0)
        self.assertEqual(live.read_bytes(), new)
        self.assertEqual(receipt['old_sha256'], sha)
        self.assertEqual(receipt['sha256'], hashlib.sha256(new).hexdigest())
        self.assertEqual(len(trash_list(self.store)['entries']), 1)
        self.assertEqual(trash_info(self.store, receipt['old_version_id'])['sha256'], sha)
        with self.assertRaises(ValueError), open(source, 'rb') as handle:
            replace_version(self.store, 'file.bin', handle.fileno(), sha, reserve_bytes=0)
        self.assertEqual(live.read_bytes(), new)
        with self.assertRaises(FileExistsError):
            restore(self.store, receipt['old_version_id'], 'file.bin', sha)
        live.unlink()
        restore(self.store, receipt['old_version_id'], 'file.bin', sha)
        self.assertEqual(live.read_bytes(), old)

    def test_budget_failure_keeps_original(self):
        live = self.root / 'file.bin'
        live.write_bytes(b'old')
        source = self.drive / 'source.bin'
        source.write_bytes(b'new')
        sha = hashlib.sha256(b'old').hexdigest()
        with self.assertRaises(ValueError), open(source, 'rb') as handle:
            replace_version(self.store, 'file.bin', handle.fileno(), sha, max_bytes=2, reserve_bytes=0)
        with self.assertRaises(OSError), open(source, 'rb') as handle:
            replace_version(self.store, 'file.bin', handle.fileno(), sha, reserve_bytes=10**18)
        self.assertEqual(live.read_bytes(), b'old')
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['file.bin'])

    def test_failed_replace_leaves_original_without_partials(self):
        live = self.root / 'file.bin'
        live.write_bytes(b'original')
        source = self.drive / 'source.bin'
        source.write_bytes(b'new')
        sha = hashlib.sha256(b'original').hexdigest()
        with patch('storage_mutations.os.replace', side_effect=OSError(5, 'io failure')):
            with self.assertRaises(OSError), open(source, 'rb') as handle:
                replace_version(self.store, 'file.bin', handle.fileno(), sha, reserve_bytes=0)
        self.assertEqual(live.read_bytes(), b'original')
        self.assertEqual(trash_list(self.store)['entries'], [])
        self.assertFalse(any(x.name.startswith('.gserver-part-') for x in self.root.iterdir()))


if __name__ == '__main__':
    unittest.main()
