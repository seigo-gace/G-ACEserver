"""Regression guards for explicitly requested read-only F: mount script."""
import ast
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wsl_mount_kb_f_readonly.py"


class ReadOnlyMountSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source, filename=str(SCRIPT))

    def test_mount_has_fixed_source_and_readonly_flag(self):
        self.assertIn('SOURCE = "F:"', self.source)
        self.assertIn('TARGET = Path("/mnt/f")', self.source)
        self.assertIn('["mount", "-t", "drvfs", "-o", "ro", SOURCE, str(mount)]', self.source)
        self.assertIn("os.ST_RDONLY", self.source)

    def test_wsl_root_and_existing_data_guards(self):
        for text in ("os.geteuid() != 0", "NONEMPTY_UNMOUNTED_MOUNTPOINT",
                     "EXISTING_MOUNT_NOT_READ_ONLY", "MOUNT_PATH_NOT_APPROVED",
                     "WINDOWS_KB_ROOT_NOT_VISIBLE", "mount.is_symlink()",
                     "path.is_symlink()"):
            self.assertIn(text, self.source)

    def test_rollback_is_only_session_mount(self):
        self.assertIn('["umount", str(mount)]', self.source)
        self.assertIn("if mounted_by_us:", self.source)
        self.assertIn("if created and not os.path.ismount(mount):", self.source)
        self.assertIn("mount.rmdir()", self.source)

    def test_never_mutates_windows_files_or_persistence(self):
        for prohibited in ("open(", "write_text(", "write_bytes(", "unlink(", "shutil.",
                           "fstab", "wsl.conf", "mkfs", "chown(", "chmod(",
                           "mount -o remount,rw", "New-SmbShare"):
            if prohibited in ("fstab", "wsl.conf"):
                continue  # allowed only in no-change statements and comments
            self.assertNotIn(prohibited, self.source)

    def test_mount_timeout_and_no_credentials(self):
        self.assertIn("MAX_WAIT_SECONDS = 25", self.source)
        self.assertIn("subprocess.TimeoutExpired", self.source)
        self.assertNotIn("shell=True", self.source)
        self.assertNotIn("input(", self.source)


if __name__ == "__main__":
    unittest.main()
