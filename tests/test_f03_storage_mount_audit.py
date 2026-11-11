"""Unit tests for read-only F03 storage mount audit."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import f03_storage_mount_audit as f03


class F03StorageMountAudit(unittest.TestCase):
    def test_not_verified_when_unmounted(self):
        with patch.object(f03.os.path, "ismount", return_value=False):
            payload = f03.audit()
        self.assertEqual(payload["f03_mount_readiness"], "NOT_VERIFIED")
        self.assertFalse(payload["g_mounted"])

    def test_pass_with_mount_and_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            mount = Path(tmp) / "g"
            files = mount / "GserverStorage" / "files"
            files.mkdir(parents=True)
            with patch.object(f03, "G_MOUNT", mount), patch.object(f03, "FILES", files), patch.object(
                f03.os.path, "ismount", return_value=True
            ), patch.object(f03, "quota", return_value={"available_bytes": 1000, "total_bytes": 2000}):
                payload = f03.audit()
        self.assertEqual(payload["quota_state"], "OK")
        self.assertEqual(payload["f03_mount_readiness"], "PASS")
        self.assertEqual(payload["usb_disconnect_test"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
