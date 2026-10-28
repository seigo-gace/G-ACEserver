"""Contract: reuse already-installed Windows KB E2E, never start a second service."""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_existing_kb_mcp_acceptance.ps1"


class WindowsKBMCPSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_reuses_both_original_kb_mcp_probes(self):
        self.assertIn("mcp_knowledge_client_e2e.py", self.text)
        self.assertIn("mcp_reusable_asset_e2e.py", self.text)
        self.assertIn("mcp-vector-search", self.text)
        self.assertIn("KB_MCP_REUSABLE_BM25_VECTOR_HYBRID_KG=PASS", self.text)

    def test_existing_active_identity_gated_and_no_fake_counts(self):
        for literal in ("modulecatalog-reusable-active.json", "runtime-state.json",
                        "DEV_KB_CURRENT_AUTHORITY_INVALID", "KB_MCP_EXPECTED_REUSABLE="):
            self.assertIn(literal, self.text)

    def test_nonpersistent_no_credential_new_agent_or_index(self):
        for banned in ("New-ScheduledTask", "Register-ScheduledTask", "git clone", "git fetch",
                       "docker run", "New-Service", "Start-Service", "New-Item", "Remove-Item",
                       "Set-Content", "Out-File", "index-knowledge-windows.ps1"):
            self.assertNotIn(banned, self.text)
        self.assertIn("MCP_ENABLE_FILE_WATCHING", self.text)
        self.assertIn("PYTHONDONTWRITEBYTECODE", self.text)
        self.assertIn("'Process'", self.text)

    def test_failure_is_not_claimed_pass_and_receipt_closed(self):
        self.assertIn("if ($LASTEXITCODE -ne 0)", self.text)
        self.assertIn("if (-not $ok) { exit 1 }", self.text)
        self.assertEqual(self.text.count("GACE_RESULT_BEGIN"), 1)
        self.assertEqual(self.text.count("GACE_RESULT_END"), 1)


if __name__ == "__main__":
    unittest.main()
