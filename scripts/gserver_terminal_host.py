#!/usr/bin/env python3
"""Minimal WSL Host boundary for the shared server-core ServerTerminal.

This process owns no dispatcher or command catalogue.  It loads the canonical
server-core delivery/ledger implementation from the existing local checkout,
delegates execution to ``gserver_host_adapter``, then returns the verified
record to the shared Result Sink over a separately authenticated endpoint.
"""
import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from gserver_host_adapter import execute_request


RECEIVER_PATH = "/internal/gserver-bounded-host"
HEALTH_PATH = "/healthz"
RESULT_PATH = "/internal/gserver-bounded-result"
RESULT_DESTINATION = "gserver-bounded-result"
MAX_BODY_BYTES = 1048576
DEFAULT_ROOT = Path("/home/gace/Project/Gserver/repository")
DEFAULT_SERVER_CORE = Path("/home/gace/server-core")
DEFAULT_STATE = Path("/home/gace/.local/state/gserver-terminal")


class HostBoundaryError(RuntimeError):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.code = code
        self.status = status


def load_shared_modules(server_core_root):
    """Load the existing same-upstream server-core checkout without copying it."""
    scripts = Path(server_core_root) / "scripts"
    if scripts.is_symlink() or not scripts.is_dir():
        raise HostBoundaryError("SERVER_CORE_SCRIPTS_UNAVAILABLE")
    scripts_text = str(scripts.resolve(strict=True))
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)
    try:
        from gace_internal_delivery_auth import read_delivery_key
        from servercore_gserver_target import receive_delivery, target_config, GserverTargetError
    except ImportError as exc:
        raise HostBoundaryError("SERVER_CORE_MODULES_UNAVAILABLE") from exc
    return read_delivery_key, receive_delivery, target_config, GserverTargetError


def load_contract(server_core_root):
    path = Path(server_core_root) / "operations" / "github-project-bounded-host.json"
    if path.is_symlink() or not path.is_file():
        raise HostBoundaryError("SERVER_CORE_CONTRACT_UNAVAILABLE")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise HostBoundaryError("SERVER_CORE_CONTRACT_INVALID") from exc
    if not isinstance(value, dict):
        raise HostBoundaryError("SERVER_CORE_CONTRACT_INVALID")
    return value


def _result_connection(endpoint):
    parsed = urlsplit(endpoint)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HostBoundaryError("RESULT_ENDPOINT_INVALID")
    if parsed.path != RESULT_PATH or not parsed.hostname:
        raise HostBoundaryError("RESULT_ENDPOINT_INVALID")
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=15)
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}:
        return http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=15)
    raise HostBoundaryError("RESULT_ENDPOINT_TLS_REQUIRED")


def send_result(record, *, endpoint, delivery_key, now=None, message_id=None):
    """Sign and send one sink record; return true only after authenticated ACK."""
    body = json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    timestamp = str(int(time.time() if now is None else now))
    message_id = message_id or ("msg_" + secrets.token_hex(12))
    signature = hmac.new(
        delivery_key, message_id.encode() + b"." + timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).digest()
    connection = _result_connection(endpoint)
    try:
        connection.request("POST", RESULT_PATH, body, {
            "content-type": "application/json",
            "x-gace-destination": RESULT_DESTINATION,
            "webhook-id": message_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": "v1," + base64.b64encode(signature).decode("ascii"),
        })
        response = connection.getresponse()
        raw = response.read(4097)
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()
    if response.status != 200 or len(raw) > 4096:
        return False
    try:
        reply = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        return False
    return isinstance(reply, dict) and reply.get("ok") is True


def make_handler(*, contract, request_key, result_key, result_endpoint, root,
                 result_dir, lock_path, receive_delivery, target_error,
                 execute=execute_request, now_fn=None):
    """Build a fixed-route handler around the shared authenticated ledger."""
    class Handler(BaseHTTPRequestHandler):
        server_version = "gace-gserver-terminal-host/1"

        def log_message(self, _format, *_args):
            return

        def send_json(self, status, payload, *, accepted=False):
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if accepted:
                self.send_header("x-gace-accepted", "true")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != HEALTH_PATH:
                self.send_json(404, {"ok": False, "error": "NOT_FOUND"})
                return
            self.send_json(200, {"ok": True, "service": "gserver-terminal-host"})

        def do_POST(self):
            if self.path != RECEIVER_PATH:
                self.send_json(404, {"ok": False, "error": "NOT_FOUND"})
                return
            try:
                try:
                    length = int(self.headers.get("content-length") or "")
                except ValueError:
                    raise HostBoundaryError("CONTENT_LENGTH_REQUIRED", 411) from None
                if not 1 <= length <= MAX_BODY_BYTES:
                    raise HostBoundaryError("BODY_SIZE_INVALID", 413)
                body = self.rfile.read(length)
                headers = {key.lower(): value for key, value in self.headers.items()}
                report = lambda record: send_result(
                    record, endpoint=result_endpoint, delivery_key=result_key,
                    now=now_fn() if now_fn else None)
                result = receive_delivery(
                    headers, body, contract=contract, delivery_key=request_key,
                    root=root, result_dir=result_dir, lock_path=lock_path,
                    execute=execute, report=report,
                    now=now_fn() if now_fn else None,
                )
                self.send_json(200, {"ok": True, "request_id": result["request_id"],
                                     "state": result["state"]}, accepted=True)
            except HostBoundaryError as exc:
                self.send_json(exc.status, {"ok": False, "error": exc.code})
            except target_error as exc:
                code = str(exc)
                status = 503 if code in {
                    "GSERVER_HOST_NOT_ADMITTED", "GSERVER_RESULT_SINK_UNAVAILABLE",
                    "GSERVER_EXECUTION_OUTCOME_UNKNOWN",
                } else 409 if code == "GSERVER_REQUEST_REPLAY_CONFLICT" else 422
                self.send_json(status, {"ok": False, "error": code})
            except Exception as exc:
                # Shared delivery authentication errors expose only their fixed
                # code/status; every other failure remains a retryable boundary.
                code = getattr(exc, "code", None)
                status = getattr(exc, "status", None)
                if isinstance(code, str) and isinstance(status, int):
                    self.send_json(status, {"ok": False, "error": code})
                else:
                    self.send_json(503, {"ok": False, "error": "GSERVER_DELIVERY_RETRYABLE"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Gserver Host adapter for shared ServerTerminal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--server-core", default=str(DEFAULT_SERVER_CORE))
    parser.add_argument("--result-endpoint", required=True)
    args = parser.parse_args()
    if args.port < 1 or args.port > 65535:
        raise SystemExit("PORT_INVALID")
    read_key, receive_delivery, target_config, target_error = load_shared_modules(args.server_core)
    contract = load_contract(args.server_core)
    if target_config(contract).get("status") != "HOST_ADMITTED":
        raise SystemExit("GSERVER_HOST_NOT_ADMITTED")
    request_key = read_key(env_prefix="GACE_GSERVER_HOST")
    result_key = read_key(env_prefix="GACE_GSERVER_RESULT")
    endpoint_check = _result_connection(args.result_endpoint)
    endpoint_check.close()
    state = DEFAULT_STATE
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(
        contract=contract, request_key=request_key, result_key=result_key,
        result_endpoint=args.result_endpoint, root=DEFAULT_ROOT,
        result_dir=state / "results", lock_path=state / "writer.lock",
        receive_delivery=receive_delivery, target_error=target_error))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
