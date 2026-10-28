import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from storage import Storage, StorageUnavailable, InvalidPath, byte_range


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.mount = Path(self.temp.name)
        self.root = self.mount / 'allowed'
        self.root.mkdir()
        self.store = Storage(str(self.mount), str(self.root))
        self.mount_check = patch('storage.os.path.ismount', return_value=True)
        self.mount_check.start()
        self.addCleanup(self.mount_check.stop)

    def test_sorted_bounded_pages(self):
        for name in ['c', 'a', 'b']:
            (self.root / name).write_bytes(name.encode())
        first = self.store.listing(limit=2)
        self.assertEqual([e['name'] for e in first['entries']], ['a', 'b'])
        self.assertEqual(first['next'], 'b')
        self.assertEqual([e['name'] for e in self.store.listing(after='b')['entries']], ['c'])

    def test_traversal_absolute_and_symlink_blocked(self):
        (self.mount / 'private').write_text('outside')
        (self.root / 'link').symlink_to(self.mount / 'private')
        (self.root / 'dirlink').symlink_to(self.mount, target_is_directory=True)
        for name in ['../private', '/etc/passwd', 'a/../../private', 'a\\b', 'link', 'dirlink/private']:
            with self.subTest(name=name), self.assertRaises((InvalidPath, StorageUnavailable)):
                with self.store.open_file(name):
                    self.fail('opened forbidden file')
        self.assertEqual(self.store.listing()['entries'], [])

    def test_hardlink_and_fifo_blocked(self):
        outside = self.mount / 'outside'
        outside.write_text('private')
        os.link(outside, self.root / 'hardlink')
        os.mkfifo(self.root / 'fifo')
        for name in ['hardlink', 'fifo']:
            with self.assertRaises(InvalidPath):
                with self.store.open_file(name):
                    self.fail('opened special file')

    def test_missing_mount_and_replaced_mount_fail_closed(self):
        self.store.listing()
        with patch('storage.os.path.ismount', return_value=False), self.assertRaises(StorageUnavailable):
            self.store.listing()
        self.store.identity = (-1, -1)
        with self.assertRaises(StorageUnavailable):
            self.store.listing()

    def test_copy_sha_for_three_sizes(self):
        for size in [0, 1024, 1048576]:
            content = os.urandom(size)
            (self.root / 'sample').write_bytes(content)
            with self.store.open_file('sample') as (fd, length, etag):
                digest = hashlib.sha256()
                while chunk := os.read(fd, 65536):
                    digest.update(chunk)
                self.assertEqual(length, size)
                self.assertEqual(digest.digest(), hashlib.sha256(content).digest())
                self.assertTrue(etag.startswith('"'))

    def test_root_must_be_subtree(self):
        for root in [str(self.mount), '/different', str(self.mount / '../outside')]:
            with self.assertRaises(InvalidPath):
                Storage(str(self.mount), root)

    def test_ranges(self):
        self.assertEqual(byte_range(None, 10), (0, 10))
        self.assertEqual(byte_range('bytes=3-5', 10), (3, 6))
        self.assertEqual(byte_range('bytes=-3', 10), (7, 10))
        self.assertEqual(byte_range('bytes=5-', 10), (5, 10))
        for value in ['bytes=10-', 'bytes=5-3', 'bytes=-0', 'bytes=1-2,3-4', 'other=1-3']:
            with self.assertRaises(ValueError):
                byte_range(value, 10)

    def test_errors_from_caller_operations_are_not_misreported_as_missing_mount(self):
        sample = self.root / 'sample'
        sample.write_bytes(b'content')
        with self.assertRaises(FileExistsError):
            with self.store.directory() as fd:
                raise FileExistsError(17, 'already exists')
        with self.assertRaises(OSError) as failure:
            with self.store.open_file('sample'):
                raise OSError(28, 'no space')
        self.assertEqual(failure.exception.errno, 28)

    def test_windows_alias_and_alternate_streams_rejected(self):
        for path in ['.. /private', 'file:secret', 'NUL', 'CON.txt', 'LPT1', 'folder./file', 'name\n']:
            with self.subTest(path=path), self.assertRaises(InvalidPath):
                with self.store.open_file(path):
                    self.fail('opened Windows alias')


if __name__ == '__main__':
    unittest.main()
