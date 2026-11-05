import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gserver_host_receiver import ReceiverError, handle_event


class GserverHostReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sha = subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT}", "rev-parse", "HEAD"],
            cwd=ROOT, text=True,
        ).strip()

    def event(self, command="printf RECEIVER_E2E"):
        request = {
            "schema": "gace.servercore-bounded-host.request/v1",
            "id": "req_" + "b" * 24,
            "command_id": "host.command",
            "expected_sha": "0" * 40,
            "repository": "seigo-gace/G-ACEserver",
            "repo_sha": self.sha,
            "command": command,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
            "host_target": "gserver",
        }
        return {
            "eventId": request["id"],
            "eventType": "gace.servercore-bounded-host.requested",
            "sourceId": "server-core-github",
            "destinationId": "gserver-bounded-host",
            "subject": "servercore-bounded-host/host.command",
            "time": "2026-11-05T00:00:00Z",
            "data": request,
        }

    def test_authenticated_event_delegates_and_correlates_result(self):
        result = handle_event(self.event(), ROOT)
        self.assertEqual(result["request_id"], "req_" + "b" * 24)
        self.assertEqual(result["host_target"], "gserver")
        self.assertEqual(result["repository"], "seigo-gace/G-ACEserver")
        self.assertEqual(result["repo_sha"], self.sha)
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "RECEIVER_E2E")

    def test_wrong_destination_is_denied_before_execution(self):
        event = self.event()
        event["destinationId"] = "server-core-bounded-host"
        with self.assertRaisesRegex(ReceiverError, "GSERVER_EVENT_ROUTE_MISMATCH"):
            handle_event(event, ROOT)

    def test_event_id_must_match_request_id(self):
        event = self.event()
        event["eventId"] = "req_" + "c" * 24
        with self.assertRaisesRegex(ReceiverError, "GSERVER_EVENT_REQUEST_MISMATCH"):
            handle_event(event, ROOT)

    def test_wrong_source_is_denied_before_execution(self):
        event = self.event()
        event["sourceId"] = "other-project"
        with self.assertRaisesRegex(ReceiverError, "GSERVER_EVENT_SOURCE_MISMATCH"):
            handle_event(event, ROOT)


if __name__ == "__main__":
    unittest.main()
