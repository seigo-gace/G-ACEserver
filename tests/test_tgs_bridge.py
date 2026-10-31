"""Gserver Bot -> durable spool -> existing Gateway TGserver ZERO lane."""
import json
import sqlite3
import threading
import time
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from tgs_bridge import (BotSpool, BotEventError, DESTINATION, PROJECT_ID, MAX_ATTEMPTS,
                        _NoGatewayRedirect, gateway_endpoint, envelope, flush_once,
                        send_gateway, gateway_token, validate)


def sample():
    return {"bot": "profile-bot", "event_id": "update-0001", "event": "bot.update.received",
            "level": "info", "outcome": "PASS", "error_code": "NONE"}


class TgsBridgeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.queue = BotSpool(self.folder / "queue")

    def test_existing_public_spool_directory_is_refused(self):
        public = self.folder / "public-queue"
        public.mkdir()
        public.chmod(0o755)
        with self.assertRaisesRegex(BotEventError, "SPOOL_DIRECTORY_UNSAFE"):
            BotSpool(public)
        self.assertFalse((public / "bot-events.sqlite3").exists())
        public.chmod(0o700)
        self.assertEqual(BotSpool(public).counts()["pending"], 0)

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

    def test_real_gateway_202_ack_is_durable_across_restart(self):
        class FakeResponse:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":"gateway-receipt"}'

        class Client:
            def open(self, *_args, **_kwargs): return FakeResponse()

        self.queue.accept(sample(), now=100)
        result = flush_once(
            self.queue, "https://gateway.example", "dummy",
            sender=lambda payload, url, token: send_gateway(payload, url, token, opener=Client()))
        self.assertEqual(result, {"sent": 1, "retry": 0, "blocked": 0})
        restarted = BotSpool(self.folder / "queue")
        self.assertEqual(restarted.counts(), {"pending": 0, "sending": 0, "blocked": 0, "sent": 1})
        self.assertIsNone(restarted.claim(now=100000))

    def test_unknown_sender_result_is_retry_not_false_ack(self):
        self.queue.accept(sample(), now=100)
        result = flush_once(self.queue, "https://gateway.example", "dummy", sender=lambda *_: "unexpected")
        self.assertEqual(result, {"sent": 0, "retry": 1, "blocked": 0})
        self.assertEqual(self.queue.counts()["pending"], 1)
        self.assertEqual(self.queue.counts()["sent"], 0)

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

    def test_blocked_gateway_delivery_requires_explicit_retry(self):
        self.queue.accept(sample(), now=100)
        flush_once(self.queue, "https://gateway.example", "token", sender=lambda *_: "blocked")
        self.assertEqual(self.queue.counts()["blocked"], 1)
        self.assertEqual(self.queue.retry_blocked(), 1)
        self.assertEqual(self.queue.counts()["pending"], 1)
        self.assertEqual(self.queue.counts()["blocked"], 0)
        sent = flush_once(self.queue, "https://gateway.example", "token", sender=lambda *_: "ack")
        self.assertEqual(sent["sent"], 1)

    def test_gateway_token_requires_private_regular_file(self):
        secret = self.folder / "gateway-token"
        secret.write_bytes(b"T" * 32)
        secret.chmod(0o644)
        with self.assertRaisesRegex(BotEventError, "GATEWAY_TOKEN_FILE_MISSING_OR_UNSAFE"):
            gateway_token(secret)
        secret.chmod(0o600)
        self.assertEqual(gateway_token(secret), "T" * 32)
        link = self.folder / "gateway-token-link"
        link.symlink_to(secret)
        with self.assertRaisesRegex(BotEventError, "GATEWAY_TOKEN_FILE_MISSING_OR_UNSAFE"):
            gateway_token(link)

    def test_wrong_gateway_url_rejected(self):
        for url in ("http://gateway.example", "https://user:pass@gateway.example",
                    "https://gateway.example/unrelated", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(BotEventError):
                gateway_endpoint(url)
        self.assertEqual(gateway_endpoint("https://gateway.example"), "https://gateway.example/internal/events")

    def test_gateway_config_lock_blocks_parallel_reader_until_writer_finishes(self):
        from tgs_bridge import gateway_configuration_lock
        folder = self.folder / "config"
        folder.mkdir(mode=0o700)
        reader_started = threading.Event()
        reader_finished = threading.Event()
        def reader():
            reader_started.set()
            with gateway_configuration_lock(folder, shared=True):
                reader_finished.set()
        with gateway_configuration_lock(folder, shared=False):
            task = threading.Thread(target=reader)
            task.start()
            self.assertTrue(reader_started.wait(1))
            self.assertFalse(reader_finished.wait(0.05))
        self.assertTrue(reader_finished.wait(1))
        task.join(timeout=1)
        self.assertFalse(task.is_alive())

    def test_gateway_config_lock_refuses_symlink_and_world_readable_lock(self):
        from tgs_bridge import gateway_configuration_lock
        folder = self.folder / "config"
        folder.mkdir(mode=0o700)
        lock = folder / "gateway-config.lock"
        lock.symlink_to(self.folder / "target")
        with self.assertRaises((BotEventError, OSError)):
            with gateway_configuration_lock(folder):
                pass
        lock.unlink()
        lock.write_text("already here")
        lock.chmod(0o644)
        with self.assertRaises(BotEventError):
            with gateway_configuration_lock(folder):
                pass

    def test_access_headers_are_optional_and_require_private_complete_pair(self):
        from tgs_bridge import gateway_access_headers
        id_file = self.folder / "cf-id"
        secret_file = self.folder / "cf-secret"
        self.assertEqual(gateway_access_headers(id_file, secret_file), {})
        id_file.write_text("testclientid1234")
        id_file.chmod(0o600)
        with self.assertRaises(BotEventError):
            gateway_access_headers(id_file, secret_file)
        secret_file.write_text("testsecretvalue1234")
        secret_file.chmod(0o600)
        self.assertEqual(gateway_access_headers(id_file, secret_file), {
            "CF-Access-Client-Id": "testclientid1234",
            "CF-Access-Client-Secret": "testsecretvalue1234",
        })
        secret_file.chmod(0o644)
        with self.assertRaises(BotEventError):
            gateway_access_headers(id_file, secret_file)
        secret_file.chmod(0o600)
        id_file.unlink()
        id_file.symlink_to(secret_file)
        with self.assertRaises(BotEventError):
            gateway_access_headers(id_file, secret_file)

    def test_access_credentials_are_separate_from_gateway_bearer(self):
        from tgs_bridge import gateway_access_headers
        cf_id = self.folder / "cf-id"
        cf_secret = self.folder / "cf-secret"
        cf_id.write_text("testclientid1234")
        cf_secret.write_text("testsecretvalue1234")
        cf_id.chmod(0o600)
        cf_secret.chmod(0o600)
        class Response:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":"gateway-uuid"}'
        class Client:
            def open(self, request, **_kwargs):
                self.headers = dict(request.header_items())
                return Response()
        client = Client()
        body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        with patch("tgs_bridge.gateway_access_headers", return_value=gateway_access_headers(cf_id, cf_secret)):
            self.assertEqual(send_gateway(body, "https://gateway.example", "gateway-bearer", opener=client), "ack")
        self.assertEqual(client.headers["Authorization"], "Bearer gateway-bearer")
        self.assertEqual(client.headers["Cf-access-client-id"], "testclientid1234")
        self.assertEqual(client.headers["Cf-access-client-secret"], "testsecretvalue1234")

    def test_gateway_post_uses_cloudflare_compatible_user_agent(self):
        from tgs_bridge import GATEWAY_USER_AGENT
        class Response:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":"gateway-id"}'
        class Client:
            request = None
            def open(self, request, **_kwargs):
                self.request = request
                return Response()
        client = Client()
        body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        self.assertEqual(send_gateway(body, "https://gateway.example",
                         "testtoken", opener=client,
                         access_headers_override={"CF-Access-Client-Id": "id-demo",
                                                  "CF-Access-Client-Secret": "secret-demo"}), "ack")
        self.assertEqual(client.request.get_header("User-agent"), GATEWAY_USER_AGENT)
        self.assertEqual(client.request.get_header("Authorization"), "Bearer testtoken")
        self.assertEqual(client.request.get_header("Cf-access-client-id"), "id-demo")

    def test_gateway_redirects_never_forward_internal_bearer(self):
        # urllib's default POST 301/302/303 handler can copy Authorization
        # to a different origin. Our handler must refuse every redirect.
        request = urllib.request.Request(
            "https://gateway.example/internal/events", data=b"{}", method="POST",
            headers={"Authorization": "Bearer dummy-internal-token"})
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.assertIsNone(_NoGatewayRedirect().redirect_request(
                    request, None, status, "redirect",
                    {"Location": "https://untrusted.example/collect"},
                    "https://untrusted.example/collect"))

    def test_redirect_response_blocks_until_gateway_url_is_repaired(self):
        class Client:
            def open(self, request, **_kwargs):
                raise urllib.error.HTTPError(
                    request.full_url, 302, "redirect",
                    {"Location": "https://untrusted.example/collect"}, None)

        body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
        self.assertEqual(send_gateway(body, "https://gateway.example",
                                      "dummy-internal-token", opener=Client()), "blocked")

    def test_real_urllib_opener_never_forwards_bearer_on_redirect(self):
        # Exercise urllib's real response/redirect chain, not just the guard
        # method in isolation. No network request leaves this fake handler.
        from email.message import Message

        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                class FakeResponse:
                    def __init__(self, url):
                        self.code = self.status = status
                        self.msg = "Redirect"
                        self.url = url
                        self.headers = Message()
                        self.headers["Location"] = "https://untrusted.example/collect"

                    def info(self): return self.headers
                    def geturl(self): return self.url
                    def read(self, *_args): return b""
                    def close(self): pass

                class FakeGateway(urllib.request.BaseHandler):
                    handler_order = 100

                    def __init__(self):
                        self.calls = []

                    def https_open(self, request):
                        self.calls.append((request.full_url,
                                           request.get_header("Authorization")))
                        return FakeResponse(request.full_url)

                gateway = FakeGateway()
                opener = urllib.request.build_opener(_NoGatewayRedirect(), gateway)
                request = urllib.request.Request(
                    "https://gateway.example/internal/events", data=b"{}",
                    method="POST", headers={"Authorization": "Bearer dummy-internal-token"})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    opener.open(request, timeout=1)
                self.assertEqual(error.exception.code, status)
                self.assertEqual(gateway.calls, [
                    ("https://gateway.example/internal/events",
                     "Bearer dummy-internal-token"),
                ])

    def test_default_gateway_opener_installs_redirect_guard(self):
        class FakeResponse:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"ok":true,"duplicate":false,"eventId":"receipt"}'

        with patch("tgs_bridge.urllib.request.build_opener") as make_opener:
            make_opener.return_value.open.return_value = FakeResponse()
            body = envelope(validate(sample()), occurred_at="2026-10-28T00:00:00Z")
            self.assertEqual(send_gateway(body, "https://gateway.example",
                                          "dummy-internal-token"), "ack")
            self.assertIsInstance(make_opener.call_args.args[0], _NoGatewayRedirect)

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

    def test_expired_last_attempt_crash_becomes_operator_blocked(self):
        # A crash after the final claim cannot leave an immortal 'sending'
        # row or schedule an undocumented attempt 21.
        self.queue.accept(sample(), now=100)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            claimed = self.queue.claim(now=100 + (attempt - 1) * 61)
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed[2], attempt)

        last_claim_time = 100 + (MAX_ATTEMPTS - 1) * 61
        self.assertIsNone(self.queue.claim(now=last_claim_time + 59))
        self.assertEqual(self.queue.counts()["sending"], 1)

        self.assertIsNone(self.queue.claim(now=last_claim_time + 61))
        self.assertEqual(self.queue.counts()["sending"], 0)
        self.assertEqual(self.queue.counts()["blocked"], 1)
        self.assertEqual(self.queue.retry_blocked(), 1)
        self.assertEqual(self.queue.counts()["pending"], 1)

    def test_stale_ack_does_not_override_newer_retry_lease(self):
        self.queue.accept(sample(), now=100)
        first = self.queue.claim(now=100)
        second = self.queue.claim(now=161)
        self.assertEqual(second[2], first[2] + 1)
        self.assertFalse(self.queue.finish(first[0], "ack", first[2], first[3], now=162))
        self.assertEqual(self.queue.counts()["sent"], 0)
        self.assertEqual(self.queue.counts()["sending"], 1)
        self.assertTrue(self.queue.finish(second[0], "retry", second[2], second[3], now=162))
        self.assertEqual(self.queue.counts()["pending"], 1)
        self.assertEqual(self.queue.counts()["sending"], 0)

    def test_old_ack_rejected_even_when_operator_retry_resets_attempt_count(self):
        self.queue.accept(sample(), now=100)
        old = self.queue.claim(now=100)
        self.assertTrue(self.queue.finish(old[0], "blocked", old[2], old[3], now=101))
        self.assertEqual(self.queue.retry_blocked(), 1)
        newer = self.queue.claim(now=102)
        self.assertEqual(old[2], newer[2])
        self.assertGreater(newer[3], old[3])
        self.assertFalse(self.queue.finish(old[0], "ack", old[2], old[3], now=103))
        self.assertEqual(self.queue.counts()["sending"], 1)
        self.assertEqual(self.queue.counts()["sent"], 0)
        self.assertTrue(self.queue.finish(newer[0], "ack", newer[2], newer[3], now=104))
        self.assertEqual(self.queue.counts()["sent"], 1)

    def test_legacy_spool_migrates_generation_without_losing_events(self):
        legacy = self.folder / "legacy-queue"
        legacy.mkdir()
        with sqlite3.connect(legacy / "bot-events.sqlite3") as conn:
            conn.execute("CREATE TABLE events (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                         "payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', "
                         "attempts INTEGER NOT NULL DEFAULT 0, next_attempt INTEGER NOT NULL DEFAULT 0, "
                         "created_at INTEGER NOT NULL, sent_at INTEGER, last_status TEXT NOT NULL DEFAULT 'queued')")
        migrated = BotSpool(legacy)
        self.assertEqual(migrated.accept(dict(sample(), event_id="migrate-1"), now=100)["status"], "queued")
        claimed = migrated.claim(now=100)
        self.assertEqual(len(claimed), 4)
        self.assertEqual(claimed[3], 1)
        self.assertTrue(migrated.finish(claimed[0], "ack", claimed[2], claimed[3], now=101))
        self.assertEqual(migrated.counts()["sent"], 1)

    def test_stale_gateway_ack_does_not_report_false_spool_success(self):
        self.queue.accept(sample())
        def reclaimed_before_ack(payload, endpoint, token):
            self.assertIsNotNone(self.queue.claim(now=int(time.time()) + 61))
            return "ack"
        result = flush_once(self.queue, "https://gateway.example", "dummy",
                            limit=1, sender=reclaimed_before_ack)
        self.assertEqual(result, {"sent": 0, "retry": 0, "blocked": 0})
        self.assertEqual(self.queue.counts()["sent"], 0)
        self.assertEqual(self.queue.counts()["sending"], 1)

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
