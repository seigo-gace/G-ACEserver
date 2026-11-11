"""Unit tests for F04 readiness orchestration."""
import unittest
from unittest.mock import patch

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gserver_f04_readiness as f04


class F04Readiness(unittest.TestCase):
    def test_not_verified_when_f_missing(self):
        with patch.object(f04, "probe", return_value={"state": "WSL_F_NOT_MOUNTED"}):
            payload = f04.audit()
        self.assertEqual(payload["f04_bridge_readiness"], "NOT_VERIFIED")

    def test_pass_when_mount_and_inspect_ok(self):
        mount = {"state": "F_KB_ROOT_READABLE", "KB_REPO_PRESENT": True}
        authority = {"current": "ACTIVE_AUTHORITY_CONSISTENT", "existing_kb_source_present": True}
        with patch.object(f04, "probe", return_value=mount), patch.object(f04, "inspect", return_value=authority):
            payload = f04.audit()
        self.assertEqual(payload["f04_bridge_readiness"], "PASS")
        self.assertEqual(payload["kb_search_e2e"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
