"""Static safety and corruption guards for the two read-only LAN probes.

PowerShell syntax is separately checked on Windows by Parser.ParseFile before execution.
"""
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

    def test_explicit_smb_and_generic_app_rules_not_conflated(self):
        fw = (ROOT / FILES[0]).read_text()
        wife = (ROOT / FILES[1]).read_text()
        for expected in (
            "HNetCfg.FwPolicy2",
            "EXPLICIT_TCP445_ALLOW_RULES=",
            "EXPLICIT_TCP445_PRIVATE_NON_SINGLE_IP_RULES=",
            "EXPLICIT_TCP445_APP_SERVICE_RESTRICTED=",
            "GENERIC_ANYPORT_APP_SERVICE_RESTRICTED=",
            "GENERIC_ANYPORT_OTHER=",
            "GENERIC_ANYPORT_OTHER_PRIVATE_NON_SINGLE_IP=",
            "GENERIC_ANYPORT_OTHER_PRIVATE_SINGLE_IP=",
            "GENERIC_ANYPORT_OTHER_NONPRIVATE=",
            "LOCAL_ADDRESS_INTERFACE_SCOPE=NOT_VERIFIED",
            "UNKNOWN_PORT_SCOPE_RULES=",
            "COUNTS_ARE_RULES_NOT_PROOF_OF_SMB_REACHABILITY",
            "$rule.ApplicationName",
            "$rule.ServiceName",
            "4000",
        ):
            self.assertIn(expected, fw)
        self.assertIn("ESU_ENROLLMENT=NOT_VERIFIED", wife)
        self.assertIn("OS_FAMILY_BY_BUILD=", wife)
        self.assertIn("MASTER_GSERVER_MARKERS=BOTH_PRESENT", wife)
        self.assertIn("HOST_ROLE_HINT=LIKELY_MASTER_GSERVER", wife)
        self.assertIn("PATCH_CURRENCY=NOT_VERIFIED", wife)
        self.assertIn("LAN_IPV4_CANDIDATE=", wife)
        self.assertIn("VIRTUAL_INTERFACE_IPV4_CANDIDATES_SKIPPED=", wife)
        self.assertIn("GetAllNetworkInterfaces()", wife)

    def test_no_truncated_regex_or_duplicate_footer(self):
        fw = (ROOT / FILES[0]).read_text()
        self.assertEqual(fw.count("========== GACE_RESULT_BEGIN =========="), 1)
        self.assertEqual(fw.count("========== GACE_RESULT_END =========="), 1)
        self.assertEqual(fw.count("FIREWALL_RULES_INSPECTED="), 1)
        self.assertEqual(fw.count("EXPLICIT_TCP445_ALLOW_RULES="), 1)
        self.assertIn("$oneIPv4 = $scope -match '^[0-9]{1,3}(\\.[0-9]{1,3}){3}$'", fw)
        self.assertIn("if (-not $oneIPv4)", fw)
        self.assertEqual(fw.count("if (-not $ok) { exit 1 }"), 1)
        self.assertTrue(fw.rstrip().endswith("if (-not $ok) { exit 1 }"))


if __name__ == "__main__":
    unittest.main()
