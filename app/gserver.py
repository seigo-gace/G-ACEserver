#!/usr/bin/env python3
import json
import hmac
import logging
import os
import shutil
import signal
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from logging.handlers import RotatingFileHandler
from urllib.parse import parse_qs, quote, urlsplit
from storage import Storage, StorageUnavailable, InvalidPath, byte_range

HOST = os.environ.get("GSERVER_BIND", "127.0.0.1")
PORT = int(os.environ.get("GSERVER_PORT", "8765"))
APP_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = Path(os.environ.get("GSERVER_LOG_DIR", str(APP_ROOT / "logs"))) / "gserver.log"
G_MOUNT = os.environ.get("GSERVER_STORAGE_ROOT", "/mnt/g")
TOKEN_FILE = os.environ.get("GSERVER_AUTH_FILE", "")
FILES_ROOT = os.environ.get("GSERVER_FILES_ROOT", "")
FILES = Storage(G_MOUNT, FILES_ROOT) if FILES_ROOT else None

logger = logging.getLogger("gserver")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
if not logger.handlers:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1048576, backupCount=4)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def disk_summary(path: str):
    if not os.path.ismount(path):
        raise OSError("storage mount unavailable")
    usage = shutil.disk_usage(path)
    stat = os.statvfs(path)
    return {
        "path": path,
        "exists": os.path.exists(path),
        "mounted": os.path.ismount(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "total_gib": round(usage.total / (1024 ** 3), 2),
        "used_gib": round(usage.used / (1024 ** 3), 2),
        "free_gib": round(usage.free / (1024 ** 3), 2),
        "block_size": stat.f_frsize,
        "available_blocks": stat.f_bavail,
    }


def authorized(header):
    # Provisioning/replacing credentials is a separate owner action. No defaults.
    if not TOKEN_FILE or not header or not header.startswith("Bearer "):
        return False
    try:
        with open(TOKEN_FILE, "rb") as stream:
            expected = stream.read(4097).strip()
        supplied = header[7:].encode("utf-8")
        return 32 <= len(expected) <= 4096 and hmac.compare_digest(expected, supplied)
    except (OSError, UnicodeError):
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "Gserver/1.0"

    def log_message(self, fmt, *args):
        # Never persist URL query, request headers, credentials or user paths.
        logger.info("http_request_completed")

    def log_request(self, code='-', size='-'):
        logger.info(json.dumps({'event_id': getattr(self, 'request_id', None),
                               'service': 'gserver', 'action': getattr(self, 'action', 'unknown'),
                               'http_status': code}, separators=(',', ':')))

    def end_headers(self):
        if hasattr(self, 'request_id'):
            self.send_header('X-Request-ID', self.request_id)
        super().end_headers()

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.request_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path = self.path.split("?", 1)[0]
        self.action = path[1:] if path in ('/health', '/status', '/ready', '/storage', '/mounts', '/files', '/download') else 'other'

        if path == "/health":
            self._json({"status": "ok", "service": "gserver"})
            return

        if path == "/":
            body = (APP_ROOT / "app" / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/ui.js":
            body = (APP_ROOT / "app" / "ui.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path not in ("/status", "/ready", "/storage", "/mounts", "/files", "/download"):
            self._json({"error": "not_found"}, status=404)
            return
        if not authorized(self.headers.get("Authorization")):
            self._json({"error": "unauthorized"}, status=401)
            return

        if path in ("/files", "/download"):
            self._files(path)
            return

        if path == "/ready":
            ready = os.path.ismount(G_MOUNT)
            self._json({"status": "ready" if ready else "storage_unavailable",
                        "storage_ready": ready,
                        "kb": "not_integrated", "tgs": "not_integrated"},
                       status=200 if ready else 503)
            return

        if path == "/status":
            payload = {
                "status": "ok",
                "service": "gserver",
                "timestamp": now,
                "uptime_seconds": round(time.monotonic() - self.server.start_ts, 2),
                "storage_ready": os.path.ismount(G_MOUNT),
                "kb": "not_integrated", "tgs": "not_integrated",
            }
            self._json(payload)
            return

        if path == "/storage" or path == "/mounts":
            try:
                summary = disk_summary(G_MOUNT)
            except OSError:
                self._json({"error": "storage_unavailable"}, status=503)
                return
            payload = {
                "target": G_MOUNT,
                "summary": summary,
                "read_only": True,
            }
            self._json(payload)
            return

    def _files(self, route):
        started = False
        try:
            if FILES is None:
                raise StorageUnavailable()
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=4)
            allowed = {'path', 'after', 'limit'} if route == '/files' else {'path'}
            if set(query) - allowed or any(len(v) != 1 for v in query.values()):
                raise InvalidPath()
            path = query.get('path', [''])[0]
            if route == '/files':
                self._json(FILES.listing(path, query.get('after', [''])[0], int(query.get('limit', ['100'])[0])))
                return
            with FILES.open_file(path) as (fd, size, etag):
                requested = self.headers.get('Range')
                if self.headers.get('If-Range') not in (None, etag):
                    requested = None
                try:
                    begin, end = byte_range(requested, size)
                except ValueError:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                self.send_response(206 if requested else 200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(end - begin))
                self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(path.split('/')[-1], safe=''))
                self.send_header('ETag', etag)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if requested:
                    self.send_header('Content-Range', f'bytes {begin}-{end - 1}/{size}')
                self.end_headers()
                started = True
                os.lseek(fd, begin, os.SEEK_SET)
                remaining = end - begin
                while remaining:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        raise StorageUnavailable()
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (InvalidPath, ValueError):
            if not started:
                self._json({'error': 'invalid_storage_request'}, 400)
        except (StorageUnavailable, OSError):
            if started:
                self.close_connection = True
            else:
                self._json({'error': 'storage_unavailable'}, 503)

class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)
        self.start_ts = time.monotonic()

    def process_request(self, request, client_address):
        request.settimeout(5)
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


if __name__ == "__main__":
    server = Server((HOST, PORT), Handler)
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    logger.info("Gserver HTTP service listening on %s:%s", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Gserver HTTP service stopped")
    finally:
        server.server_close()
