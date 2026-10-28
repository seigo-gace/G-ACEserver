"""Basic static safety contract for read-only host/client LAN probes."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = ["scripts/windows_lan_firewall_readonly.ps1",
         "scripts/windows_wife_lan_readonly.ps1"]


class LanProbes(unittest.TestCase):
    def test_no_mutation_or_unbounded_query(self):
        for filename in FILES:
            with self.subTest(filename=filename):
                body = (ROOT / filename).read_text()
                for forbidden in ("New-SmbShare", "Set-SmbShare", "New-LocalUser",
                                  "New-NetFirewallRule", "Set-NetFirewallRule",
                                  "Set-Acl ", "Remove-Item", "netsh advfirewall"):
                    self.assertNotIn(forbidden, body)
                self.assertIn("CHANGES=NONE", body)
                self.assertIn("VERIFY=PASS", body)
                self.assertIn("VERIFY=FAIL", body)

    def test_version_and_firewall_specificity(self):
        fw = (ROOT / FILES[0]).read_text()
        win = (ROOT / FILES[1]).read_text()
        self.assertIn("HNetCfg.FwPolicy2", fw)
        self.assertIn("BROAD_SCOPE_PRIVATE_TCP445_ALLOW_RULES=", fw)
        self.assertIn("4000", fw)
        self.assertIn("ESU_ENROLLMENT=NOT_VERIFIED", win)
        self.assertIn("LAN_IPV4_CANDIDATE=", win)
        self.assertIn("GetAllNetworkInterfaces()", win)

    def test_firewall_script_regression_no_broken_regex_or_duplicate_tail(self):
        fw = (ROOT / FILES[0]).read_text()
        self.assertEqual(fw.count("========== GACE_RESULT_BEGIN =========="), 1)
        self.assertEqual(fw.count("========== GACE_RESULT_END =========="), 1)
        self.assertEqual(fw.count("FIREWALL_RULES_INSPECTED="), 1)
        self.assertEqual(fw.count("BROAD_SCOPE_PRIVATE_TCP445_ALLOW_RULES="), 1)
        self.assertIn("$singleIPv4 = $scope -match '^[0-9]{1,3}(\\.[0-9]{1,3}){3}$'", fw)
        self.assertIn("if (-not $singleIPv4 -and", fw)
        self.assertEqual(fw.count("if (-not $ok) { exit 1 }"), 1)
        self.assertTrue(fw.rstrip().endswith("if (-not $ok) { exit 1 }"))

if __name__ == "__main__":
    unittest.main()
