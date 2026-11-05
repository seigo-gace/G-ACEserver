import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gserver_host_adapter as adapter


class GserverHostAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "test"], check=True)
        (self.root / "marker.txt").write_text("ok")
        subprocess.run(["git", "-C", str(self.root), "add", "marker.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "fixture"], check=True)
        self.sha = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        command = "printf adapter-pass"
        self.request = {
            "schema": "gace.servercore-bounded-host.request/v1", "id": "req_" + "a" * 24,
            "command_id": "host.command", "expected_sha": "b" * 40,
            "repository": adapter.REPOSITORY, "repo_sha": self.sha,
            "command": command, "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
            "host_target": adapter.TARGET,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_execute_returns_target_and_hash_correlated_result(self):
        result = adapter.execute_request(self.request, self.root)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["host_sha"], self.sha)
        self.assertEqual(result["stdout_sha256"], hashlib.sha256(b"adapter-pass").hexdigest())
        self.assertEqual(result["stderr_sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(result["dispatcher_sha"], self.request["expected_sha"])
        self.assertEqual(result["command_sha256"], self.request["command_sha256"])

    def test_normal_development_write_git_and_home_are_available(self):
        command = "printf changed > generated.txt; git add generated.txt; printf %s \"$HOME\""
        value = dict(self.request, command=command,
                     command_sha256=hashlib.sha256(command.encode()).hexdigest())
        result = adapter.execute_request(value, self.root)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["stdout"], os.path.expanduser("~"))
        self.assertEqual((self.root / "generated.txt").read_text(), "changed")
        staged = subprocess.check_output(
            ["git", "-C", str(self.root), "diff", "--cached", "--name-only"], text=True)
        self.assertEqual(staged.strip(), "generated.txt")

    def test_timeout_is_configurable_for_long_development_jobs(self):
        self.assertEqual(adapter.command_timeout({}), 3600)
        self.assertEqual(adapter.command_timeout({"GSERVER_TERMINAL_COMMAND_TIMEOUT_SECONDS": "7200"}), 7200)
        for invalid in ("0", "21601", "bad"):
            with self.assertRaisesRegex(adapter.HostAdapterError, "TIMEOUT_INVALID"):
                adapter.command_timeout({"GSERVER_TERMINAL_COMMAND_TIMEOUT_SECONDS": invalid})

    def test_unknown_schema_rejected_before_execution(self):
        with self.assertRaisesRegex(adapter.HostAdapterError, "SCHEMA_INVALID"):
            adapter.execute_request(dict(self.request, schema="other/v1"), self.root)

    def test_non_utf8_output_hash_matches_returned_text(self):
        command = "printf '\\377'"
        value = dict(self.request, command=command,
                     command_sha256=hashlib.sha256(command.encode()).hexdigest())
        result = adapter.execute_request(value, self.root)
        self.assertEqual(result["stdout"], "\ufffd")
        self.assertEqual(result["stdout_sha256"], hashlib.sha256(result["stdout"].encode()).hexdigest())

    def test_wrong_repo_sha_and_changed_command_are_rejected(self):
        with self.assertRaisesRegex(adapter.HostAdapterError, "REPO_SHA_MISMATCH"):
            adapter.execute_request(dict(self.request, repo_sha="c" * 40), self.root)
        with self.assertRaisesRegex(adapter.HostAdapterError, "TRANSPORT_CHANGED"):
            adapter.execute_request(dict(self.request, command="printf changed"), self.root)

    def test_no_docker_or_fixed_command_surface(self):
        source = (ROOT / "scripts/gserver_host_adapter.py").read_text()
        self.assertNotIn("docker.sock", source)
        self.assertNotIn("listen(", source)
        self.assertNotIn("allowed_commands", source)


if __name__ == "__main__":
    unittest.main()
