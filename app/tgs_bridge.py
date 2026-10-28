"""Durable, bounded Bot operational events for the EXISTING Gateway -> TGserver ZERO lane.

No message body, user/chat ID or Telegram token is accepted or stored here.
At-least-once HTTP delivery uses stable sourceId/eventId and Gateway 202 receipt.
"""
import hashlib
import contextlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROJECT_ID = "P015"  # must be provisioned on the real TGserver before remote use
DESTINATION = "tgserver-zero-bulk"
BOT = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
KIND = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,47}$")
MAX_PENDING = 5000
MAX_SENT_RECEIPTS = 20000
MAX_ATTEMPTS = 20
MAX_BODY = 4096
ALLOWED = {"bot.started", "bot.stopped", "bot.error", "bot.recovered",
           "bot.request.completed", "bot.request.failed", "bot.update.received",
           "bot.delivery.completed", "bot.delivery.failed"}
LEVELS = {"info", "warn", "error"}
OUTCOMES = {"PASS", "FAIL", "RETRY", "SKIP"}
SAFE_ID = re.compile(r"^[a-z0-9-]{3,96}$")


class BotEventError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def validate(value):
    if not isinstance(value, dict) or set(value) - {"bot", "event_id", "event", "level", "outcome", "error_code"}:
        raise BotEventError("INVALID_EVENT_SCHEMA")
    bot, eid, event = value.get("bot"), value.get("event_id"), value.get("event")
    if not isinstance(bot, str) or not BOT.fullmatch(bot):
        raise BotEventError("INVALID_BOT")
    if not isinstance(eid, str) or not EVENT_ID.fullmatch(eid):
        raise BotEventError("INVALID_EVENT_ID")
    if not isinstance(event, str) or event not in ALLOWED:
        raise BotEventError("INVALID_EVENT")
    level = value.get("level", "info")
    outcome = value.get("outcome", "PASS")
    code = value.get("error_code", "NONE")
    if not isinstance(level, str) or not isinstance(outcome, str) or level not in LEVELS or outcome not in OUTCOMES:
        raise BotEventError("INVALID_LEVEL_OR_OUTCOME")
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise BotEventError("INVALID_ERROR_CODE")
    if outcome == "FAIL" and level == "info":
        raise BotEventError("FAIL_MUST_BE_WARNING_OR_ERROR")
    return {"bot": bot, "event_id": eid, "event": event, "level": level,
            "outcome": outcome, "error_code": code}


def envelope(value, *, occurred_at):
    data = {"event": value["event"], "bot": value["bot"],
            "outcome": value["outcome"], "error_code": value["error_code"],
            "event_id": value["event_id"]}
    message = json.dumps(data, sort_keys=True, separators=(",", ":"))
    log = {"project_id": PROJECT_ID, "severity": value["level"],
           "hint": "gserver-bot-runtime", "timestamp": occurred_at,
           "message": message}
    return {"eventId": "gserver:" + value["bot"] + ":" + value["event_id"],
            "eventType": "gserver.bot.operation", "sourceId": "gserver-bot",
            "destinationId": DESTINATION,
            "data": {"logs": [log]}}


def secure_dir(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or (path.exists() and not path.is_dir()):
        raise BotEventError("SPOOL_DIRECTORY_UNSAFE")
    if not path.exists():
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink():
        raise BotEventError("SPOOL_DIRECTORY_UNSAFE")
    return path


class BotSpool:
    def __init__(self, directory):
        self.directory = secure_dir(directory)
        self.database = self.directory / "bot-events.sqlite3"
        if self.database.is_symlink():
            raise BotEventError("SPOOL_DATABASE_SYMLINK")
        self._init()

    def connect(self):
        if self.database.is_symlink():
            raise BotEventError("SPOOL_DATABASE_SYMLINK")
        conn = sqlite3.connect(str(self.database), timeout=4, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=4000")
        return conn

    def _init(self):
        with contextlib.closing(self.connect()) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
                sent_at INTEGER, last_status TEXT NOT NULL DEFAULT 'queued')""")
            conn.execute("CREATE INDEX IF NOT EXISTS events_ready ON events(state,next_attempt)")
        try:
            os.chmod(self.database, 0o600)
        except OSError:
            pass

    def accept(self, value, now=None):
        event = validate(value)
        now = int(time.time() if now is None else now)
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
        packed = json.dumps(envelope(event, occurred_at=stamp), sort_keys=True, separators=(",", ":"))
        key = "gserver:" + event["bot"] + ":" + event["event_id"]
        # Idempotency compares the original Bot event, not the first-accept timestamp.
        # Replays after restart/delay must remain duplicates, not false conflicts.
        fingerprint = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with contextlib.closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT fingerprint FROM events WHERE id=?", (key,)).fetchone()
            if old:
                if not hmac.compare_digest(old[0], fingerprint):
                    raise BotEventError("EVENT_ID_CONFLICT")
                return {"status": "duplicate", "queued": True}
            pending = conn.execute("SELECT COUNT(*) FROM events WHERE state != 'sent'").fetchone()[0]
            if pending >= MAX_PENDING:
                raise BotEventError("SPOOL_FULL")
            conn.execute("INSERT INTO events(id,fingerprint,payload,created_at) VALUES(?,?,?,?)",
                         (key, fingerprint, packed, now))
            return {"status": "queued", "queued": True}

    def retry_blocked(self, limit=100):
        """Explicit operator repair after correcting 401/409/422; no automatic loops."""
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise BotEventError("RETRY_LIMIT_INVALID")
        with contextlib.closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT id FROM events WHERE state='blocked' ORDER BY created_at,id LIMIT ?",
                                (limit,)).fetchall()
            conn.executemany("UPDATE events SET state='pending',attempts=0,next_attempt=0,last_status='operator_retry' WHERE id=?",
                             rows)
            return len(rows)

    def counts(self):
        with contextlib.closing(self.connect()) as conn, conn:
            values = dict(conn.execute("SELECT state,COUNT(*) FROM events GROUP BY state").fetchall())
            return {"pending": values.get("pending", 0), "sending": values.get("sending", 0),
                    "blocked": values.get("blocked", 0), "sent": values.get("sent", 0)}

    def claim(self, now=None):
        now = int(time.time() if now is None else now)
        with contextlib.closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id,payload,attempts FROM events WHERE state IN ('pending','sending') "
                "AND next_attempt<=? AND attempts<? ORDER BY created_at,id LIMIT 1",
                (now, MAX_ATTEMPTS)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE events SET state='sending',next_attempt=?,attempts=attempts+1 WHERE id=?",
                         (now + 60, row[0]))
            return row[0], json.loads(row[1]), row[2] + 1

    def finish(self, key, status, attempts, now=None):
        now = int(time.time() if now is None else now)
        if status not in ("ack", "retry", "blocked"):
            raise BotEventError("BAD_DELIVERY_STATUS")
        state = "sent" if status == "ack" else ("blocked" if status == "blocked" or attempts >= MAX_ATTEMPTS else "pending")
        delay = min(3600, 15 * 2 ** min(attempts, 8))
        with contextlib.closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE events SET state=?,next_attempt=?,sent_at=?,last_status=? WHERE id=? AND state='sending'",
                         (state, now + delay if state == "pending" else 0, now if state == "sent" else None,
                          status if state != "blocked" else "requires_operator", key))
            # Retain successful receipts for 7 days to deduplicate replays.
            conn.execute("DELETE FROM events WHERE state='sent' AND sent_at<?", (now - 7 * 86400,))
            # A bounded retention window is necessary on a small owner PC.
            conn.execute("""DELETE FROM events WHERE id IN (
                SELECT id FROM events WHERE state='sent'
                ORDER BY sent_at DESC,id DESC LIMIT -1 OFFSET ?
            )""", (MAX_SENT_RECEIPTS,))


def gateway_endpoint(url):
    if not isinstance(url, str) or not url or len(url) > 300:
        raise BotEventError("GATEWAY_URL_NOT_CONFIGURED")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise BotEventError("GATEWAY_URL_UNSAFE")
    if parsed.path not in ("", "/", "/internal/events"):
        raise BotEventError("GATEWAY_ENDPOINT_UNSUPPORTED")
    return url.rstrip("/") if parsed.path == "/internal/events" else url.rstrip("/") + "/internal/events"


def gateway_token(path):
    file = Path(path)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > 4096:
        raise BotEventError("GATEWAY_TOKEN_FILE_MISSING_OR_UNSAFE")
    token = file.read_bytes().strip()
    if not 24 <= len(token) <= 4096 or any(ch <= 32 or ch >= 127 for ch in token):
        raise BotEventError("GATEWAY_TOKEN_INVALID")
    return token.decode("ascii")


class _NoGatewayRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward an internal API bearer credential across redirects."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_gateway(payload, endpoint, token, opener=None):
    request = urllib.request.Request(
        gateway_endpoint(endpoint), data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    client = opener if opener is not None else urllib.request.build_opener(_NoGatewayRedirect())
    try:
        with client.open(request, timeout=5) as response:
            code = response.status
            body = response.read(65536)
        parsed = json.loads(body)
        if code != 202 or not isinstance(parsed, dict) or parsed.get("ok") is not True or parsed.get("duplicate") not in (True, False):
            return "retry"
        # The Gateway returns its OWN persistent event UUID, not necessarily the
        # producer-supplied idempotency eventId. Do not compare those two IDs.
        if not isinstance(parsed.get("eventId"), str) or not parsed["eventId"]:
            return "retry"
        return "ack"
    except urllib.error.HTTPError as error:
        # A redirect means the private internal endpoint is misconfigured.
        # Require operator repair; never allow an automatic bearer replay.
        if 300 <= error.code < 400 or error.code in (400, 401, 403, 409, 413, 422):
            return "blocked"
        return "retry"
    except (OSError, ValueError, TimeoutError):
        return "retry"


def flush_once(spool, url, token, *, limit=10, sender=send_gateway):
    if not 1 <= limit <= 50:
        raise BotEventError("FLUSH_LIMIT_INVALID")
    done = {"sent": 0, "retry": 0, "blocked": 0}
    for _ in range(limit):
        claimed = spool.claim()
        if claimed is None:
            break
        key, payload, attempts = claimed
        try:
            result = sender(payload, url, token)
        except Exception:
            result = "retry"
        # "ack" is the sender result, while "sent" is only the metric key.
        # Do not validate delivery outcomes against the metric dictionary.
        if result not in ("ack", "retry", "blocked"):
            result = "retry"
        spool.finish(key, result, attempts)
        done["sent" if result == "ack" else result] += 1
    return done
