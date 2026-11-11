import base64
import hashlib
import hmac
import http.client
import json
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

    def host_server(self, receive, endpoint):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        handler = terminal.make_handler(
            contract={"contract": True}, request_key=b"request-key",
            result_key=b"result-key", result_endpoint=endpoint, root=ROOT,
            result_dir=Path(tmp.name) / "results", lock_path=Path(tmp.name) / "lock",
            receive_delivery=receive, target_error=TargetError,
            execute=lambda request, root: None, now_fn=lambda: NOW,
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return server.server_address[1]

    def post_host(self, port, body=b"{}", path=terminal.RECEIVER_PATH):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("POST", path, body, {"content-type": "application/json"})
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


if __name__ == "__main__":
    unittest.main()
