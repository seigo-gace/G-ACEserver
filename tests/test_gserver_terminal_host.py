import base64
import hashlib
import hmac
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gserver_terminal_host as terminal


NOW = 1700000000
REQUEST_ID = "req_" + "1" * 24


class TargetError(ValueError):
    pass


class TerminalHostTests(unittest.TestCase):
    def result_server(self, key=b"result-key", status=200, response=None):
        received = []

        class Sink(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):
                length = int(self.headers["content-length"])
                body = self.rfile.read(length)
                signature = base64.b64decode(self.headers["webhook-signature"][3:])
                signed = (self.headers["webhook-id"].encode() + b"." +
                          self.headers["webhook-timestamp"].encode() + b"." + body)
                received.append({
                    "path": self.path, "destination": self.headers["x-gace-destination"],
                    "body": json.loads(body),
                    "signature_ok": hmac.compare_digest(
                        signature, hmac.new(key, signed, hashlib.sha256).digest()),
                })
                payload = json.dumps(response or {"ok": True, "state": "RECORDED"}).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        endpoint = f"http://127.0.0.1:{server.server_address[1]}{terminal.RESULT_PATH}"
        return endpoint, received

    def host_server(self, receive, endpoint, **overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        handler = terminal.make_handler(
            contract={"contract": True}, request_key=b"request-key",
            result_key=b"result-key", result_endpoint=endpoint, root=ROOT,
            result_dir=Path(tmp.name) / "results", lock_path=Path(tmp.name) / "lock",
            receive_delivery=receive, target_error=TargetError,
            execute=lambda request, root: None, now_fn=lambda: NOW,
            **overrides,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return server.server_address[1]

    def post_host(self, port, body=b"{}", path=terminal.RECEIVER_PATH, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        request_headers = {"content-type": "application/json"}
        request_headers.update(headers or {})
        connection.request("POST", path, body, request_headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_result_sender_uses_fixed_route_destination_and_hmac(self):
        endpoint, received = self.result_server()
        record = {"schema": "gace.servercore-bounded-result.record/v1",
                  "request_id": REQUEST_ID}
        self.assertTrue(terminal.send_result(
            record, endpoint=endpoint, delivery_key=b"result-key", now=NOW,
            message_id="msg_1234567890abcdef12345678"))
        self.assertEqual(received[0]["path"], terminal.RESULT_PATH)
        self.assertEqual(received[0]["destination"], terminal.RESULT_DESTINATION)
        self.assertTrue(received[0]["signature_ok"])
        self.assertEqual(received[0]["body"], record)

    def test_result_sender_rejects_non_tls_remote_endpoint(self):
        with self.assertRaisesRegex(terminal.HostBoundaryError, "RESULT_ENDPOINT_TLS_REQUIRED"):
            terminal.send_result({}, endpoint="http://example.com:80" + terminal.RESULT_PATH,
                                 delivery_key=b"result-key")

    def test_listener_delegates_to_shared_receiver_and_requires_sink_ack(self):
        endpoint, returned = self.result_server()
        calls = []

        def receive(headers, body, **kwargs):
            calls.append((headers, body, kwargs))
            record = {"schema": "gace.servercore-bounded-result.record/v1",
                      "request_id": REQUEST_ID}
            if kwargs["report"](record) is not True:
                raise TargetError("GSERVER_RESULT_SINK_UNAVAILABLE")
            return {"request_id": REQUEST_ID, "state": "PASS"}

        status, body = self.post_host(self.host_server(receive, endpoint), b'{"safe":true}')
        self.assertEqual((status, body),
                         (200, {"ok": True, "request_id": REQUEST_ID, "state": "PASS"}))
        self.assertEqual(calls[0][1], b'{"safe":true}')
        self.assertEqual(calls[0][2]["root"], ROOT)
        self.assertEqual(calls[0][2]["delivery_key"], b"request-key")
        self.assertEqual(returned[0]["body"]["request_id"], REQUEST_ID)

    def test_listener_never_reports_success_when_result_sink_rejects(self):
        endpoint, _ = self.result_server(status=503, response={"ok": False})

        def receive(_headers, _body, **kwargs):
            if kwargs["report"]({"schema": "x"}) is not True:
                raise TargetError("GSERVER_RESULT_SINK_UNAVAILABLE")

        status, body = self.post_host(self.host_server(receive, endpoint))
        self.assertEqual((status, body["error"]),
                         (503, "GSERVER_RESULT_SINK_UNAVAILABLE"))

    def test_listener_rejects_unregistered_path_before_shared_receiver(self):
        endpoint, _ = self.result_server()
        calls = []
        status, body = self.post_host(
            self.host_server(lambda *a, **k: calls.append((a, k)), endpoint),
            path="/not-terminal")
        self.assertEqual((status, body["error"]), (404, "NOT_FOUND"))
        self.assertEqual(calls, [])

    def test_blocklisted_request_authenticates_and_skips_without_execution_or_report(self):
        endpoint, returned = self.result_server()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            marker = root / "reset-mode.json"
            marker.write_text(json.dumps({
                "schema": terminal.RESET_MARKER_SCHEMA,
                "state": "ACTIVE",
                "activated_at": "2026-11-24T11:00:00+09:00",
                "reason": "owner reset",
                "blocked_request_ids": [REQUEST_ID],
            }), encoding="utf-8")
            os.chmod(marker, 0o600)
            receipts = root / "skipped"
            calls = {"receive": 0, "verify": 0, "validate": 0}

            def receive(*_args, **_kwargs):
                calls["receive"] += 1
                raise AssertionError("reset mode must not execute delivery")

            def verify(_headers, _body, **kwargs):
                calls["verify"] += 1
                self.assertEqual(kwargs["expected_destination"], "gserver-bounded-host")

            def validate(request, _contract):
                calls["validate"] += 1
                self.assertEqual(request["id"], REQUEST_ID)

            request = {
                "schema": "gace.servercore-bounded-host.request/v1",
                "id": REQUEST_ID,
                "command_id": "host.command",
                "expected_sha": "a" * 40,
                "repository": "seigo-gace/G-ACEserver",
                "repo_sha": "b" * 40,
                "command": "true",
                "command_sha256": hashlib.sha256(b"true").hexdigest(),
                "host_target": "gserver",
            }
            body_bytes = json.dumps(request).encode()
            port = self.host_server(
                receive, endpoint,
                verify_delivery=verify,
                validate_transport_request=validate,
                target_config=lambda _contract: {
                    "transport": {"destination_id": "gserver-bounded-host"},
                },
                reset_marker=marker,
                reset_receipt_dir=receipts,
            )
            status, response = self.post_host(port, body_bytes)
            self.assertEqual(status, 410)
            self.assertEqual(response["error"], "GSERVER_RESET_SKIPPED")
            self.assertEqual(calls, {"receive": 0, "verify": 1, "validate": 1})
            self.assertEqual(returned, [])
            receipt = json.loads((receipts / (REQUEST_ID + ".json")).read_text())
            self.assertEqual(receipt["state"], "SKIPPED")
            self.assertNotIn("command", receipt)
            self.assertEqual(oct((receipts / (REQUEST_ID + ".json")).stat().st_mode & 0o777),
                             "0o600")

    def test_unblocked_request_continues_through_normal_receiver(self):
        endpoint, _ = self.result_server()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            marker = root / "reset-mode.json"
            marker.write_text(json.dumps({
                "schema": terminal.RESET_MARKER_SCHEMA,
                "state": "ACTIVE",
                "activated_at": "2026-11-24T11:00:00+09:00",
                "reason": "owner reset",
                "blocked_request_ids": ["req_" + "2" * 24],
            }), encoding="utf-8")
            os.chmod(marker, 0o600)
            calls = {"receive": 0, "verify": 0, "validate": 0}

            def receive(_headers, _body, **_kwargs):
                calls["receive"] += 1
                return {"request_id": REQUEST_ID, "state": "PASS"}

            def verify(*_args, **_kwargs):
                calls["verify"] += 1

            def validate(request, _contract):
                calls["validate"] += 1
                self.assertEqual(request["id"], REQUEST_ID)

            request = {
                "schema": "gace.servercore-bounded-host.request/v1",
                "id": REQUEST_ID,
                "command_id": "host.command",
                "expected_sha": "a" * 40,
                "repository": "seigo-gace/G-ACEserver",
                "repo_sha": "b" * 40,
                "command": "true",
                "command_sha256": hashlib.sha256(b"true").hexdigest(),
                "host_target": "gserver",
            }
            port = self.host_server(
                receive, endpoint,
                verify_delivery=verify,
                validate_transport_request=validate,
                target_config=lambda _contract: {
                    "transport": {"destination_id": "gserver-bounded-host"},
                },
                reset_marker=marker,
                reset_receipt_dir=root / "skipped",
            )
            status, response = self.post_host(port, json.dumps(request).encode())
            self.assertEqual(status, 200)
            self.assertEqual(response["request_id"], REQUEST_ID)
            self.assertEqual(calls, {"receive": 1, "verify": 1, "validate": 1})

    def test_unsafe_reset_marker_fails_closed_before_execution(self):
        endpoint, _ = self.result_server()
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "reset-mode.json"
            marker.write_text("{}", encoding="utf-8")
            os.chmod(marker, 0o644)
            calls = []
            port = self.host_server(
                lambda *args, **kwargs: calls.append((args, kwargs)), endpoint,
                reset_marker=marker,
                reset_receipt_dir=Path(root) / "skipped",
            )
            status, response = self.post_host(port)
            self.assertEqual((status, response["error"]),
                             (503, "RESET_MARKER_UNSAFE"))
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
