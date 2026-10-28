"""No-write tests for F: mount detection."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gserver_kb_mount_probe as probe


class MountProbeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name)
        self.mount = self.parent / "f"
        self.kb = self.mount / "G-ACE-KB"
        self.entry = "4 1 0:1 / " + str(self.mount) + " rw - 9p F: rw"

    def test_missing_mount(self):
        self.assertEqual(probe.probe(self.mount, self.kb)["state"], "WSL_F_PATH_MISSING")

    def test_unmounted_folder_does_not_count(self):
        self.kb.mkdir(parents=True)
        self.assertEqual(probe.probe(self.mount, self.kb, [])["state"], "WSL_F_NOT_MOUNTED")

    def test_valid_explicit_mount(self):
        self.kb.mkdir(parents=True)
        with patch.object(probe.os.path, "ismount", return_value=True):
            result = probe.probe(self.mount, self.kb, [self.entry])
        self.assertEqual(result["state"], "F_KB_ROOT_READABLE")
        self.assertFalse(result["KB_ACTIVE_MARKER_PRESENT"])

    def test_mount_exists_without_kb_root(self):
        self.mount.mkdir()
        with patch.object(probe.os.path, "ismount", return_value=True):
            result = probe.probe(self.mount, self.kb, [self.entry])
        self.assertEqual(result["state"], "F_MOUNTED_KB_ROOT_ABSENT")

    def test_parent_mount_not_accepted(self):
        self.kb.mkdir(parents=True)
        parent_entry = "4 1 0:1 / " + str(self.parent) + " rw - 9p F: rw"
        with patch.object(probe.os.path, "ismount", return_value=True):
            result = probe.probe(self.mount, self.kb, [parent_entry])
        self.assertEqual(result["state"], "WSL_F_NOT_MOUNTED")

    def test_symlinked_root_refused(self):
        self.mount.mkdir()
        other = self.parent / "other"
        other.mkdir()
        self.kb.symlink_to(other, target_is_directory=True)
        self.assertEqual(probe.probe(self.mount, self.kb)["state"], "SYMLINK_REFUSED")

    def test_invalid_root_fails(self):
        self.mount.mkdir()
        with self.assertRaises(ValueError):
            probe.probe(self.mount, self.parent, [])

    def test_malformed_mountinfo_ignored(self):
        self.assertIsNone(probe.mount_fs(self.mount, ["bad file", "abc - def"]))


if __name__ == "__main__":
    unittest.main()
