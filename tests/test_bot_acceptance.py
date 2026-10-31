"""Packaging and acceptance failure regressions; these are not Docker evidence."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bot_acceptance as acceptance
import gserver_bot_ready as ready
from gserverctl import Controller


class BotAcceptanceTests(unittest.TestCase):
    def test_failed_acceptance_restores_previous_release_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            control = Mock()
            old = {"current": "sha256:" + "a" * 64, "access": "loopback", "storage": True}
            control.load.return_value = old
            control.run.return_value = Mock(stdout="sha256:" + "b" * 64)
            with patch.object(ready, "STATE", Path(folder)), \
                 patch.object(ready, "Controller", return_value=control), \
                 patch.object(ready, "docker_preflight"), \
                 patch.object(acceptance, "verify", side_effect=RuntimeError("BOT_REPLAY_FAILED")), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "BOT_REPLAY_FAILED"):
                    ready.install()
            control.activate.assert_called_with(old["current"], access="loopback", storage=True)
            control.save.assert_called_once_with(old)

    def test_allowlisted_build_context_can_import_application(self):
        # Reproduce the repository's deny-all + explicit-file Docker context.
        entries = (ROOT / ".dockerignore").read_text().splitlines()
        self.assertEqual(entries[0], "**")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for entry in entries[1:]:
                self.assertTrue(entry.startswith("!"))
                relative = entry[1:]
                source = ROOT / relative
                if source.is_file():
                    destination = target / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
            env = dict(os.environ, GSERVER_LOG_DIR=str(target / "logs"))
            result = subprocess.run([sys.executable, "-I", "-B", "-c",
                                     "import sys; sys.path.insert(0, 'app'); import gserver"],
                                    cwd=target, env=env, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_owner_auth_is_present_once_in_every_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            control = Controller(Path(folder))
            for access, storage in (("isolated", False), ("loopback", False), ("loopback", True)):
                body = control.bundle("sha256:" + "c" * 64, create=True,
                                      access=access, storage=storage).read_text()
                self.assertEqual(body.count("GSERVER_AUTH_FILE:"), 1)

    def test_sudo_failure_is_diagnostic_without_private_stderr(self):
        control = Mock()
        control.run.side_effect = subprocess.CalledProcessError(
            1, ["private-command"], stderr="sudo: a password is required\nprivate-details")
        with self.assertRaisesRegex(RuntimeError, "^DOCKER_SUDO_AUTH_REQUIRED$"):
            ready.docker_preflight(control)

    def test_other_docker_failure_does_not_echo_private_stderr(self):
        control = Mock()
        control.run.side_effect = subprocess.CalledProcessError(1, [], stderr="private-details")
        with self.assertRaisesRegex(RuntimeError, "^DOCKER_LOCAL_ACCESS_FAILED$"):
            ready.docker_preflight(control)

    def fake_control(self):
        import hashlib
        control = Mock()
        control.load.return_value = {"current": "sha256:" + "a" * 64}
        info = {"Image": control.load.return_value["current"], "NetworkSettings": {
            "Ports": {"8765/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18765"}]}}}
        hashes = {n: hashlib.sha256((ROOT / "app" / n).read_bytes()).hexdigest()
                  for n in ("gserver.py", "storage.py", "kb_source.py", "tgs_bridge.py")}
        control.run.side_effect = [
            Mock(stdout=json.dumps(info)), Mock(stdout=json.dumps(hashes)),
            Mock(stdout=json.dumps(["b" * 32, "o" * 32])),
            Mock(stdout="d" * 64), Mock(stdout="d" * 64)]
        return control

    def responses(self):
        return [(200, {}), (401, {}), (401, {}), (401, {}), (200, {}),
                (202, {"status": "queued"}), (202, {"status": "duplicate"}),
                (409, {}), (202, {"status": "duplicate"}), (409, {})]

    def test_stop_start_and_replay_are_required_for_pass(self):
        control = self.fake_control()
        output = io.StringIO()
        with patch.object(acceptance, "request", side_effect=self.responses()), contextlib.redirect_stdout(output):
            acceptance.verify(control)
        self.assertEqual([call.args[0] for call in control.action.call_args_list], ["stop", "start"])
        self.assertIn("BOT_SQLITE_STOP_START_PERSISTENCE=PASS", output.getvalue())
        self.assertNotIn("b" * 32, output.getvalue())
        self.assertNotIn("o" * 32, output.getvalue())

    def test_stop_failure_still_attempts_start_and_never_reports_pass(self):
        control = self.fake_control()
        control.action.side_effect = [subprocess.CalledProcessError(1, []), None]
        output = io.StringIO()
        with patch.object(acceptance, "request", side_effect=self.responses()), contextlib.redirect_stdout(output):
            with self.assertRaises(subprocess.CalledProcessError):
                acceptance.verify(control)
        self.assertEqual([call.args[0] for call in control.action.call_args_list], ["stop", "start"])
        self.assertNotIn("=PASS", output.getvalue())

    def test_replay_loss_after_restart_is_not_pass(self):
        responses = self.responses()
        responses[-2] = (202, {"status": "queued"})
        with patch.object(acceptance, "request", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "BOT_REPLAY_FAILED"):
                acceptance.verify(self.fake_control())


if __name__ == "__main__":
    unittest.main()
