"""Contract verification for isolated LAN inbox source; no Windows modifications."""
from pathlib import Path
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts" / "windows_lan_inbox.ps1").read_text()


class InboxScriptContracts(unittest.TestCase):
    def test_unmodified_parent_and_no_share(self):
        for banned in ("New-SmbShare", "Set-SmbShare", "Remove-SmbShare",
                       "New-LocalUser", "New-NetFirewallRule", "Set-NetFirewallRule",
                       "Remove-NetFirewallRule", "Set-SmbServerConfiguration"):
            self.assertNotIn(banned, SCRIPT)
        self.assertIn("G:\\GserverStorage\\files\\LAN-Inbox", SCRIPT)
        self.assertIn("SetAccessRuleProtection($true, $false)", SCRIPT)
        self.assertIn("G_PARENT_ACL_CHANGED=False", SCRIPT)
        self.assertIn("INBOX_BROAD_ALLOW_COUNT=0", SCRIPT)

    def test_new_only_and_explicit_prepare(self):
        self.assertIn("param([switch]$Prepare)", SCRIPT)
        self.assertIn("ALREADY_PRESENT_UNTOUCHED", SCRIPT)
        self.assertIn("if ([IO.Directory]::Exists($target) -or [IO.File]::Exists($target))", SCRIPT)
        self.assertIn("elseif (-not $Prepare)", SCRIPT)
        self.assertIn("CHANGES=NONE", SCRIPT)
        self.assertIn("Set-Acl -LiteralPath $target", SCRIPT)
        self.assertNotIn("Remove-Item", SCRIPT)
        self.assertNotIn("RemoveDirectory", SCRIPT)
        self.assertNotIn("Format-Volume", SCRIPT)

if __name__ == "__main__":
    unittest.main()
