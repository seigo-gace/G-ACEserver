"""Unit tests for read-only F01 WSL boot audit helpers."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import audit_f01_wsl_boot as f01


class F01WslBootAudit(unittest.TestCase):
    def test_read_wsl_conf_parses_boot_systemd(self):
        with tempfile.TemporaryDirectory() as root:
            conf = Path(root) / 'wsl.conf'
            conf.write_text('[boot]\nsystemd=true\n# comment\n')
            with patch.object(f01, 'WSL_CONF', conf):
                parsed = f01.read_wsl_conf()
        self.assertEqual(parsed["boot_systemd"], "true")

    def test_audit_passes_when_stack_ready(self):
        wsl = {"present": True, "boot_systemd": "true"}
        docker = {"reachable": True, "server_version": "29.9.2"}
        services = [
            {"unit": "docker.service", "is_enabled": "enabled", "is_active": "active"},
            {"unit": "containerd.service", "is_enabled": "enabled", "is_active": "active"},
        ]
        with patch.object(f01, "read_wsl_conf", return_value=wsl), patch.object(
            f01, "docker_summary", return_value=docker
        ), patch.object(f01, "compose_version", return_value={"available": True}), patch.object(
            f01, "unit_state", side_effect=services
        ):
            payload = f01.audit()
        self.assertEqual(payload["f01_partial_wsl_layer"], "PASS")
        self.assertEqual(payload["windows_reboot_recovery"], "NOT_VERIFIED")

    def test_audit_not_verified_without_systemd_boot(self):
        with patch.object(f01, "read_wsl_conf", return_value={"present": True, "boot_systemd": "false"}), patch.object(
            f01, "docker_summary", return_value={"reachable": True}
        ), patch.object(f01, "compose_version", return_value={"available": False}), patch.object(
            f01, "unit_state", return_value={"is_active": "active", "is_enabled": "enabled"}
        ):
            payload = f01.audit()
        self.assertEqual(payload["f01_partial_wsl_layer"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
