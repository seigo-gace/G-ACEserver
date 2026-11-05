import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TerminalDeployContractTests(unittest.TestCase):
    def test_user_service_is_loopback_nonroot_and_uses_external_secret_files(self):
        unit = (ROOT / "deploy" / "gserver-terminal-host.service").read_text(encoding="utf-8")
        env = (ROOT / "deploy" / "gserver-terminal-host.env.example").read_text(encoding="utf-8")
        self.assertIn("--host 127.0.0.1", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectHome=read-only", unit)
        self.assertIn("ReadWritePaths=/home/gace/.local/state/gserver-terminal", unit)
        self.assertNotIn("User=root", unit)
        self.assertNotIn("0.0.0.0", unit)
        self.assertIn("GACE_GSERVER_HOST_HMAC_KEY_FILE=", env)
        self.assertIn("GACE_GSERVER_RESULT_HMAC_KEY_FILE=", env)
        self.assertIn("GACE_GSERVER_RESULT_ENDPOINT=https://", env)
        for forbidden in ("HMAC_KEY=", "TOKEN=", "PASSWORD="):
            self.assertNotIn(forbidden, env)


if __name__ == "__main__":
    unittest.main()
