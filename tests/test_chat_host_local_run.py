import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import chat_host_local_run as run
from chat_host_registration import install

SHA = "a" * 40
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def sample_request():
    return {
        "request_id": "req_123456789abc",
        "project": "Gserver",
        "change_unit": "GSR-CHAT-HOST-01",
        "repository": "seigo-gace/G-ACEserver",
        "source_sha": SHA,
        "command_id": "project.git_head",
        "effect": "read_only",
        "issued_at": NOW.isoformat(),
    }


class LocalRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reg = install(self.root, path=self.root / "reg.json")
        self.ledger = self.root / "claims.sqlite"

    @patch("chat_host_local_run.inspect_once", return_value={"request_id": "req_123456789abc", "result": {"head_matches": True}})
    @patch("chat_host_local_run.datetime")
    def test_success(self, now_fn, inspect):
        now_fn.now.return_value = NOW
        payload = run.run_request(
            sample_request(),
            registration_path=self.reg,
            ledger_path=self.ledger,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["request_id"], "req_123456789abc")

    @patch("chat_host_local_run.inspect_once", side_effect=__import__("chat_host_ledger").ReplayDenied("DUPLICATE_REQUEST"))
    @patch("chat_host_local_run.datetime")
    def test_duplicate(self, now_fn, inspect):
        now_fn.now.return_value = NOW
        payload = run.run_request(sample_request(), registration_path=self.reg, ledger_path=self.ledger)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "DUPLICATE_REQUEST")

    def test_main_invalid_json(self):
        buf = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO("not-json")):
            with patch.object(sys, "stdout", buf):
                code = run.main()
        self.assertEqual(code, 1)
        self.assertIn("REQUEST_JSON_INVALID", buf.getvalue())
