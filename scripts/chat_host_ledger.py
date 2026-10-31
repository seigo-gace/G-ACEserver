"""Durable single-host request-id claim ledger; never performs commands.

Requires an independently authenticated sender, admitted local host, restricted
state-directory ownership, and a verified execution boundary. No transport here.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import re

class ReplayDenied(ValueError):
    pass

def canonical_fingerprint(request: dict) -> str:
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

class RequestLedger:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def claim(self, request_id: str, fingerprint: str) -> bool:
        """True only for a newly durably claimed request; repeated IDs fail closed."""
        if not isinstance(request_id, str) or not re.fullmatch(r"req_[a-z0-9]{12,40}", request_id):
            raise ReplayDenied("REQUEST_ID_INVALID")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ReplayDenied("FINGERPRINT_INVALID")
        path = self.db_path
        if not isinstance(path, Path) or path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
            raise ReplayDenied("LEDGER_PATH_INVALID")
        if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
            raise ReplayDenied("LEDGER_FILE_INVALID")
        if path.exists() and path.stat().st_mode & 0o077:
            raise ReplayDenied("LEDGER_PERMISSIONS_INVALID")
        previous = os.umask(0o077)
        try:
            with sqlite3.connect(path, timeout=2, isolation_level=None) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("CREATE TABLE IF NOT EXISTS claims (request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM claims WHERE request_id=?", (request_id,)).fetchone():
                    db.execute("ROLLBACK")
                    return False
                db.execute("INSERT INTO claims VALUES (?,?)", (request_id, fingerprint))
                db.execute("COMMIT")
                return True
        except sqlite3.Error as exc:
            raise ReplayDenied("LEDGER_UNAVAILABLE") from exc
        finally:
            os.umask(previous)
