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

if __name__ == "__main__":
    unittest.main()
