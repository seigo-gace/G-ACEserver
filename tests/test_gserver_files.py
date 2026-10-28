"""Offline tests for Gserver's host-side create-only file transfers."""
import errno
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
spec = importlib.util.spec_from_file_location("transfer", ROOT / "scripts/gserver_files.py")
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.drive = Path(self.tmp.name) / "drive"
        self.files = self.drive / "GserverStorage" / "files"
        self.files.mkdir(parents=True)
        self.incoming = Path(self.tmp.name) / "incoming"
        self.incoming.mkdir()
        self.downloads = Path(self.tmp.name) / "downloads"
        self.downloads.mkdir()
        mount = patch("gserver_files.os.path.ismount", return_value=True)
        # The module is loaded via a custom spec; patch directly to avoid import aliases.
        self.check = patch.object(transfer.os.path, "ismount", return_value=True)
        self.check.start()
        self.addCleanup(self.check.stop)

    def upload(self, source):
        return transfer.put(str(source), self.drive, self.files)

    def download(self, name):
        return transfer.get(name, str(self.downloads), self.drive, self.files)

    def test_round_trip_hash_and_no_overwrite(self):
        data = os.urandom(1024 * 1024 + 75)
        source = self.incoming / "video.mp4"
        source.write_bytes(data)
        receipt = self.upload(source)
        self.assertEqual(receipt["bytes"], len(data))
        self.assertEqual(receipt["sha256"], __import__("hashlib").sha256(data).hexdigest())
        self.assertEqual((self.files / "video.mp4").read_bytes(), data)
        with self.assertRaises(FileExistsError):
            self.upload(source)
        self.assertEqual(self.download("video.mp4")["sha256"], receipt["sha256"])
        self.assertEqual((self.downloads / "video.mp4").read_bytes(), data)
        with self.assertRaises(FileExistsError):
            self.download("video.mp4")

    def test_existing_symlink_and_out_of_scope_paths_rejected(self):
        outside = self.incoming / "private.txt"
        outside.write_text("do-not-change")
        (self.files / "private.txt").symlink_to(outside)
        with self.assertRaises(FileExistsError):
            self.upload(outside)
        self.assertEqual(outside.read_text(), "do-not-change")
        with self.assertRaises((transfer.InvalidPath, transfer.StorageUnavailable)):
            self.download("../private.txt")
        (self.incoming / "linked").symlink_to(outside)
        with self.assertRaises(OSError):
            self.upload(self.incoming / "linked")

    def test_missing_drive_mount_fails_closed(self):
        local = self.incoming / "data.txt"
        local.write_text("a")
        with patch.object(transfer.os.path, "ismount", return_value=False):
            with self.assertRaises(transfer.StorageUnavailable):
                self.upload(local)
        self.assertFalse((self.files / "data.txt").exists())

    def test_failed_partial_write_leaves_no_published_file(self):
        source = self.incoming / "data.txt"
        source.write_text("hello")
        real_write = transfer.os.write
        with patch.object(transfer.os, "write", side_effect=OSError(errno.ENOSPC, "full")):
            with self.assertRaises(OSError):
                self.upload(source)
        self.assertEqual(list(self.files.iterdir()), [])

    def test_listing_uses_existing_storage_guards(self):
        source = self.incoming / "movie.mkv"
        source.write_bytes(b"12345")
        self.upload(source)
        listing = transfer.list_files(self.drive, self.files)
        self.assertEqual(listing["entries"], [{"name": "movie.mkv", "kind": "file", "size": 5}])


if __name__ == "__main__":
    unittest.main()
