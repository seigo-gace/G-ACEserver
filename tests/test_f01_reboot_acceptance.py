"""Tests for the F01 before/after reboot evidence contract."""
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import f01_reboot_acceptance as reboot


def snapshot(windows="win-a", wsl="wsl-a", ready=True):
    return {
        "schema": reboot.SCHEMA,
        "captured_at_utc": "2026-11-05T00:00:00+00:00",
        "windows_boot_id": windows,
        "wsl_boot_id": wsl,
        "wsl_audit": {
            "wsl_systemd_boot_configured": True,
            "docker_stack_running": ready,
            "f01_partial_wsl_layer": "PASS" if ready else "NOT_VERIFIED",
        },
        "core_container": {
            "present": ready,
            "state": "running" if ready else "exited",
            "health": "healthy" if ready else "unhealthy",
        },
        "core_health": {"reachable": ready, "http_status": 200 if ready else 503},
    }


class F01RebootAcceptanceTests(unittest.TestCase):
    def test_compare_passes_only_after_both_boots_change_and_runtime_recovers(self):
        result = reboot.compare(snapshot(), snapshot("win-b", "wsl-b"))
        self.assertEqual(result["windows_reboot_recovery"], "PASS")
        self.assertEqual(result["windows_autostart_to_wsl"], "NOT_VERIFIED")
        self.assertEqual(result["verify"], "PASS")

    def test_compare_rejects_same_windows_boot(self):
        result = reboot.compare(snapshot(), snapshot("win-a", "wsl-b"))
        self.assertEqual(result["windows_reboot_recovery"], "NOT_VERIFIED")
        self.assertEqual(result["verify"], "FAIL")

    def test_compare_rejects_runtime_failure(self):
        result = reboot.compare(snapshot(), snapshot("win-b", "wsl-b", ready=False))
        self.assertEqual(result["windows_reboot_recovery"], "NOT_VERIFIED")
        self.assertFalse(result["docker_stack_recovered"])

    def test_private_atomic_evidence_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "private" / "before.json"
            reboot.write_private_json(path, snapshot())
            loaded = reboot.load_evidence(path)
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(loaded["schema"], reboot.SCHEMA)
        self.assertEqual(mode, 0o600)

    def test_load_rejects_wrong_schema(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "before.json"
            path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
            with self.assertRaisesRegex(reboot.EvidenceError, "SCHEMA_MISMATCH"):
                reboot.load_evidence(path)

    def test_capture_command_does_not_claim_reboot_acceptance(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "before.json"
            with patch.object(reboot, "capture_snapshot", return_value=snapshot()):
                code = reboot.main(["capture", "--evidence", str(path)])
            payload = reboot.load_evidence(path)
        self.assertEqual(code, 0)
        self.assertEqual(payload["windows_boot_id"], "win-a")


if __name__ == "__main__":
    unittest.main()
