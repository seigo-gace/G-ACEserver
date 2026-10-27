"""Static contract for isolated staging of the real existing Gserver source."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "scripts" / "smoke_gserver_staging.sh"
COMPOSE = ROOT / "deploy" / "compose.gserver.staging.yaml"

class GserverStagingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SH.read_text()
        cls.compose = COMPOSE.read_text()

    def test_shell_syntax(self):
        p = subprocess.run(["bash", "-n", str(SH)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_source_is_read_only_and_exact(self):
        self.assertIn("41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c", self.script)
        self.assertIn("source: ${GSERVER_SOURCE_FILE:?source_file_required}", self.compose)
        self.assertIn("read_only: true", self.compose)

    def test_no_external_service_or_network(self):
        self.assertIn('network_mode: "none"', self.compose)
        self.assertNotIn("ports:", self.compose)
        self.assertNotIn("docker.sock", self.compose)
        self.assertIn('HOST_PORTS=NONE', self.script)

    def test_compose_env_passed_via_sudo(self):
        self.assertNotIn("sudo timeout", self.script)
        self.assertIn('sudo env GSERVER_SOURCE_FILE="$GSERVER_SOURCE_FILE" timeout', self.script)
        self.assertEqual(self.script.count('sudo env GSERVER_SOURCE_FILE="$GSERVER_SOURCE_FILE" timeout'), 5)

    def test_contained_lifecycle(self):
        self.assertIn("STAGING_PROJECT_ALREADY_EXISTS", self.script)
        self.assertIn('down --timeout 10', self.script)
        self.assertIn('started=1', self.script)
        self.assertNotIn("--remove-orphans", self.script)
        self.assertNotIn('rm -rf', self.script)

    def test_minimal_image_privileges(self):
        for item in ('user: "65534:65534"', "cap_drop:", "no-new-privileges:true", "read_only: true", "mem_limit: 256m", "pids_limit: 64"):
            self.assertIn(item, self.compose)

    def test_public_repo_secret_safety(self):
        for item in ("secret:", "password:", "token:", "Authorization:"):
            self.assertNotIn(item, self.compose)
        self.assertIn("SOURCE_MUTATIONS=NONE", self.script)

    def test_gace_result_contract(self):
        for item in ("GACE_RESULT_BEGIN", "GACE_RESULT_END", "PROJECT_END=Gserver", "VERIFY=PASS", "VERIFY=FAIL"):
            self.assertIn(item, self.script)

if __name__ == "__main__":
    unittest.main()
