"""Gserver Bot -> durable spool -> existing Gateway TGserver ZERO lane."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from tgs_bridge import (BotSpool, BotEventError, DESTINATION, PROJECT_ID,
                        gateway_endpoint, envelope, flush_once, send_gateway,
                        validate)


def sample():
    return {"bot": "profile-bot", "event_id": "update-0001", "event": "bot.update.received",
            "level": "info", "outcome": "PASS", "error_code": "NONE"}


class TgsBridgeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.queue = BotSpool(self.folder / "queue")

    def test_only_bounded_operational_fields_accepted(self):
        for payload in (
            dict(sample(), text="private telegram message"),
            dict(sample(), chat_id=12345),
            dict(sample(), user_id="private"),
            dict(sample(), event="bot.command.execute"),
            dict(sample(), bot="../outside"),
            dict(sample(), event_id="../../etc/passwd"),
            dict(sample(), error_code="custom secret"),
        ):
            with self.subTest(payload=list(payload)), self.assertRaises(BotEventError):
                self.queue.accept(payload)
        self.assertEqual(self.queue.counts()["pending"], 0)

    def test_durable_enqueue_and_restart_idempotent(self):
        self.assertEqual(self.queue.accept(sample(), now=100)["status"], "queued")
        other = BotSpool(self.folder / "queue")
        self.assertEqual(other.accept(sample(), now=777)["status"], "duplicate")
        self.assertEqual(other.counts()["pending"], 1)
        row = other.claim(now=100)
        self.assertEqual(row[1]["eventId"], "gserver:profile-bot:update-0001")
        self.assertEqual(row[1]["destinationId"], DESTINATION)
        self.assertEqual(row[1]["data"]["logs"][0]["project_id"], PROJECT_ID)

    def test_replay_changed_payload_is_conflict(self):
        self.queue.accept(sample(), now=100)
        changed = dict(sample(), outcome="SKIP")
        with self.assertRaisesRegex(BotEventError, "EVENT_ID_CONFLICT"):
            self.queue.accept(changed, now=101)
        self.assertEqual(self.queue.counts()["pending"], 1)

    def test_successful_202_is_only_ack_and_no_requeue(self):
        self.queue.accept(sample(), now=100)
        res = flush_once(self.queue, "https://gateway.example", "dummy", sender=lambda *_: "ack")
        self.assertEqual(res, {"sent": 1, "retry": 0, "blocked": 0})
        self.assertEqual(self.queue.counts()["sent"], 1)
        self.assertEqual(self.queue.claim(now=100000), None)

    def test_failure_keeps_unsent_until_retry(self):
        self.queue.accept(sample(), now=100)
        res = flush_once(self.queue, "https://gateway.example", "dummy", sender=lambda *_: "retry")
        self.assertEqual(res["retry"], 1)
        self.assertEqual(self.queue.counts()["pending"], 1)

    def test_401_is_blocked_not_false_delivered(self):
        self.queue.accept(sample(), now=100)
        res = flush_once(self.queue, "https://gateway.example", "dummy", sender=lambda *_: "blocked")
        self.assertEqual(res["blocked"], 1)
        self.assertEqual(self.queue.counts()["blocked"], 1)
        self.assertEqual(self.queue.counts()["sent"], 0)

    def test_wrong_gateway_url_rejected(self):
        for url in ("http://gateway.example", "https://user:pass@gateway.example",
                    "https://gateway.example/unrelated", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(BotEventError):
                gateway_endpoint(url)
        self.assertEqual(gateway_endpoint("https://gateway.example"), "https://gateway.example/internal/events")

    def test_exact_log_contract_and_no_user_data(self):
        payload = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        self.assertEqual(payload["sourceId"], "gserver-bot")
        self.assertEqual(payload["data"]["logs"][0]["severity"], "info")
        self.assertEqual(payload["data"]["logs"][0]["project_id"], PROJECT_ID)
        self.assertEqual(set(json.loads(payload["data"]["logs"][0]["message"])),
                         {"bot", "event", "event_id", "outcome", "error_code"})

    def test_spool_limit_rejects_extra_event(self):
        with patch("tgs_bridge.MAX_PENDING", 1):
            self.queue.accept(sample(), now=100)
            with self.assertRaisesRegex(BotEventError, "SPOOL_FULL"):
                self.queue.accept(dict(sample(), event_id="update-2"), now=101)

    def test_claim_lease_retries_after_crash_and_stable_payload(self):
        self.queue.accept(sample(), now=100)
        first = self.queue.claim(now=100)
        self.assertIsNone(self.queue.claim(now=105))
        second = self.queue.claim(now=161)
        self.assertEqual(first[1], second[1])
        self.assertEqual(second[2], 2)

    def test_gateway_generated_receipt_id_is_accepted(self):
        class FakeResponse:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":"gateway-uuid-123"}'
        class Client:
            def open(self, *_args, **_kwargs): return FakeResponse()
        body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        self.assertEqual(send_gateway(body, "https://gateway.example", "testtoken", opener=Client()), "ack")

    def test_unhashable_field_is_rejected_as_validation_error(self):
        with self.assertRaises(BotEventError):
            self.queue.accept(dict(sample(), event=["invalid"]))
        with self.assertRaises(BotEventError):
            self.queue.accept(dict(sample(), level=["error"]))

    def test_bad_202_receipt_keeps_event(self):
        class FakeResponse:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":""}'
        class Client:
            def open(self, *_args, **_kwargs): return FakeResponse()
        body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        self.assertEqual(send_gateway(body, "https://gateway.example", "testtoken", opener=Client()), "retry")


if __name__ == "__main__":
    unittest.main()
