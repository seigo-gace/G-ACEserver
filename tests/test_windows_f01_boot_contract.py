"""Static safety checks for the read-only Windows F01 boot audit script."""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_f01_boot_readonly.ps1"


class WindowsF01BootContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = SCRIPT.read_text()

    def test_read_only_envelope(self):
        for marker in ("GACE_RESULT_BEGIN", "GACE_RESULT_END", "CHANGES=NONE", "VERIFY=PASS", "VERIFY=FAIL"):
            self.assertIn(marker, self.body)

    def test_no_scheduled_task_mutation(self):
        forbidden = (
            "Register-ScheduledTask",
            "New-ScheduledTask",
            "Set-ScheduledTask",
            "Start-Process wsl",
            "wsl --shutdown",
            "Set-Content",
            "Remove-Item",
        )
        for token in forbidden:
            self.assertNotIn(token, self.body)

    def test_reports_not_verified_recovery(self):
        self.assertIn("WINDOWS_REBOOT_RECOVERY=NOT_VERIFIED", self.body)
        self.assertIn("WSL_DIRECT_SCHEDULED_TASK_COUNT=", self.body)


if __name__ == "__main__":
    unittest.main()
