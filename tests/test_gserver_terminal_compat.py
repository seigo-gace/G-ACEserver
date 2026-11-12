import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gserver_terminal_compat as compat
import gserver_terminal_host as host


class CompatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "--allow-empty", "-qm", "fixture"], check=True)
        self.sha = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        self.env = {compat.FLAG: "1"}

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **kwargs):
        values = dict(request_id="req_" + "a" * 24, project_repository="seigo-gace/GateApp-Bot",
                      command="git rev-parse HEAD", expected_sha="b" * 40, root=self.root,
                      operation_class="read", env=self.env)
        values.update(kwargs)
        return compat.build_request(**values)

    def test_default_environment_is_disabled_before_git(self):
        self.assertFalse(compat.enabled({}))
        with self.assertRaisesRegex(compat.CompatError, "COMPAT_DISABLED"):
            compat.build_request(request_id="req_" + "a" * 24, project_repository="seigo-gace/GateApp-Bot",
                                 command="git status", expected_sha="b" * 40, root=Path("/missing"),
                                 env={})

    def test_enabled_read_keeps_mandatory_sha_fields(self):
        request = self.build()
        self.assertEqual(set(request), {"schema", "id", "command_id", "expected_sha", "repository",
                                        "repo_sha", "command", "command_sha256", "host_target"})
        self.assertEqual(request["repo_sha"], self.sha)
        self.assertEqual(request["expected_sha"], "b" * 40)
        self.assertNotIn("--sha", request["command"])
        self.assertEqual(request["command_sha256"], hashlib.sha256(request["command"].encode()).hexdigest())

    def test_missing_dispatcher_sha_is_refused(self):
        with self.assertRaisesRegex(compat.CompatError, "DISPATCHER_SHA_REQUIRED"):
            self.build(expected_sha=None)

    def test_write_without_pin_is_refused(self):
        with self.assertRaisesRegex(compat.CompatError, "WRITE_PIN_REQUIRED"):
            self.build(operation_class="write")

    def test_explicit_project_pin_is_carried_and_not_executed(self):
        request = self.build(explicit_sha="c" * 40)
        self.assertIn("--sha", request["command"])
        self.assertIn("c" * 40, request["command"])

    def test_host_repository_pin_must_match_measured_head(self):
        with self.assertRaisesRegex(compat.CompatError, "HOST_SHA_MISMATCH"):
            self.build(project_repository="seigo-gace/G-ACEserver", explicit_sha="d" * 40)

    def test_resident_host_does_not_import_the_flag(self):
        text = Path(host.__file__).read_text(encoding="utf-8")
        self.assertNotIn(compat.FLAG, text)
        self.assertNotIn("gserver_terminal_compat", text)


if __name__ == "__main__":
    unittest.main()
