"""Static safety checks for WSL Docker bootstrap; not a runtime/installer test."""
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install_wsl_docker_compose.sh"

class DockerBootstrapContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = SCRIPT.read_text()

    def test_bash_syntax(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_wsl_and_source_guards(self):
        for token in ("/mnt/g/Project/Gserver", "NOT_WSL", "UNSUPPORTED_OS", "SOURCE_SHA_CHANGED"):
            self.assertIn(token, self.body)

    def test_official_key_pinning(self):
        self.assertIn("9DC858229FC7DD38854AE2D88D81803C0EBFCD88", self.body)
        self.assertIn("https://download.docker.com/linux/ubuntu", self.body)

    def test_non_destructive_dependency_simulation(self):
        self.assertIn("apt-get -o DPkg::Lock::Timeout=30 -s install", self.body)
        self.assertIn("ERROR=APT_WOULD_REMOVE_INSTALLED_PACKAGES", self.body)
        self.assertNotIn("apt-get remove", self.body)
        self.assertNotIn("autoremove", self.body)

    def test_isolated_no_public_ports(self):
        self.assertIn("network_mode: none", self.body)
        self.assertIn("DOCKER_COMPOSE_SMOKE=PASS;PUBLISHED_PORTS=NONE", self.body)
        self.assertNotIn("--publish", self.body)

    def test_no_credential_or_service_tampering(self):
        for forbidden in ("usermod", "docker group", "podman.socket stop", "systemctl stop", "docker system prune", "rm -rf", "curl | bash", "docker login"):
            self.assertNotIn(forbidden, self.body)

    def test_result_envelope_and_timeouts(self):
        for marker in ("GACE_RESULT_BEGIN", "GACE_RESULT_END", "PROJECT_END=Gserver", "VERIFY=PASS", "VERIFY=FAIL"):
            self.assertIn(marker, self.body)
        self.assertIn("timeout 900", self.body)
        self.assertIn("timeout 180", self.body)

if __name__ == '__main__':
    unittest.main()
