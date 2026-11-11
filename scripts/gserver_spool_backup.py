#!/usr/bin/env python3
"""Bounded, encrypted backup and isolated restore for the Gserver Bot spool.

This owns only the local Gserver SQLite spool. It does not contact TGserver,
Gateway, Vault or Cloudflare, and never stores the encryption key in the archive.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
import time

SCHEMA = "gserver.bot-spool-backup.v1"
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024
NONCE_BYTES = 12
KEY_BYTES = 32

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - exercised by capability checks
    AESGCM = None


class BackupError(Exception):
    pass


def _regular_private(path, *, directory=False):
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise BackupError("BACKUP_PATH_MISSING_OR_SYMLINK")
    info = path.stat()
    if directory:
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise BackupError("BACKUP_DIRECTORY_UNSAFE")
    elif not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise BackupError("BACKUP_FILE_UNSAFE")
    return path


def _new_private_dir(path):
    path = Path(path)
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise BackupError("BACKUP_OUTPUT_MUST_BE_NEW")
    path.mkdir(mode=0o700)
    return path


def _key(raw):
    if not isinstance(raw, bytes) or len(raw) != KEY_BYTES:
        raise BackupError("BACKUP_KEY_MUST_BE_32_BYTES")
    if AESGCM is None:
        raise BackupError("BACKUP_CRYPTOGRAPHY_UNAVAILABLE")
    return raw


def read_key(stream):
    raw = stream.buffer.read(KEY_BYTES + 1)
    if len(raw) != KEY_BYTES:
        raise BackupError("BACKUP_KEY_MUST_BE_32_BYTES")
    return _key(raw)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _sqlite_snapshot(spool):
    spool = _regular_private(spool, directory=True)
    source = spool / "bot-events.sqlite3"
    _regular_private(source)
    with tempfile.TemporaryDirectory(prefix="gserver-spool-snapshot-") as tmp:
        target = Path(tmp) / "bot-events.sqlite3"
        src_uri = "file:" + str(source) + "?mode=ro"
        src = sqlite3.connect(src_uri, uri=True)
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
            src.close()
        data = target.read_bytes()
    if not data or len(data) > MAX_SNAPSHOT_BYTES:
        raise BackupError("BACKUP_SNAPSHOT_SIZE_INVALID")
    return data


def _check_sqlite(data):
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise BackupError("BACKUP_SNAPSHOT_SIZE_INVALID")
    with tempfile.NamedTemporaryFile(prefix="gserver-restore-check-", suffix=".sqlite3") as temp:
        temp.write(data)
        temp.flush()
        conn = sqlite3.connect("file:" + temp.name + "?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA quick_check").fetchone()
            if result != ("ok",):
                raise BackupError("BACKUP_SQLITE_QUICK_CHECK_FAILED")
        finally:
            conn.close()


def create_backup(spool, archive, key):
    key = _key(key)
    plaintext = _sqlite_snapshot(Path(spool))
    _check_sqlite(plaintext)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, SCHEMA.encode())
    archive = _new_private_dir(archive)
    try:
        payload = archive / "payload.enc"
        manifest = archive / "manifest.json"
        payload.write_bytes(ciphertext)
        os.chmod(payload, 0o600)
        record = {
            "schema": SCHEMA,
            "created_at": int(time.time()),
            "source": "gserver-bot-spool",
            "cipher": "AES-256-GCM",
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "plaintext_bytes": len(plaintext),
            "plaintext_sha256": _sha256(plaintext),
            "ciphertext_bytes": len(ciphertext),
            "ciphertext_sha256": _sha256(ciphertext),
        }
        manifest.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
        os.chmod(manifest, 0o600)
        return record
    except Exception:
        shutil.rmtree(archive)
        raise


def _read_archive(archive, key):
    key = _key(key)
    archive = _regular_private(archive, directory=True)
    manifest_path = _regular_private(archive / "manifest.json")
    payload_path = _regular_private(archive / "payload.enc")
    try:
        record = json.loads(manifest_path.read_text())
        if record.get("schema") != SCHEMA or record.get("cipher") != "AES-256-GCM":
            raise BackupError("BACKUP_MANIFEST_INVALID")
        nonce = base64.b64decode(record["nonce_b64"], validate=True)
        if len(nonce) != NONCE_BYTES:
            raise BackupError("BACKUP_NONCE_INVALID")
        ciphertext = payload_path.read_bytes()
        if len(ciphertext) != record.get("ciphertext_bytes") or _sha256(ciphertext) != record.get("ciphertext_sha256"):
            raise BackupError("BACKUP_CIPHERTEXT_HASH_MISMATCH")
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, SCHEMA.encode())
        except Exception as exc:
            raise BackupError("BACKUP_DECRYPTION_FAILED") from exc
        if len(plaintext) != record.get("plaintext_bytes") or _sha256(plaintext) != record.get("plaintext_sha256"):
            raise BackupError("BACKUP_PLAINTEXT_HASH_MISMATCH")
        _check_sqlite(plaintext)
        return record, plaintext
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("BACKUP_MANIFEST_INVALID") from exc


def verify_backup(archive, key):
    record, plaintext = _read_archive(archive, key)
    return {"schema": record["schema"], "plaintext_bytes": len(plaintext),
            "plaintext_sha256": _sha256(plaintext), "verified": True}


def restore_backup(archive, output, key):
    record, plaintext = _read_archive(archive, key)
    output = Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise BackupError("RESTORE_OUTPUT_MUST_BE_NEW")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".gserver-restore-", dir=output.parent))
    try:
        db = temp / "bot-events.sqlite3"
        db.write_bytes(plaintext)
        os.chmod(db, 0o600)
        receipt = temp / "restore-manifest.json"
        receipt.write_text(json.dumps({"schema": record["schema"],
                                       "plaintext_sha256": record["plaintext_sha256"],
                                       "plaintext_bytes": record["plaintext_bytes"]},
                                      sort_keys=True, indent=2) + "\n")
        os.chmod(receipt, 0o600)
        os.replace(temp, output)
        return {"restored": str(output), "plaintext_bytes": len(plaintext),
                "plaintext_sha256": _sha256(plaintext), "verified": True}
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify", "restore"))
    parser.add_argument("--spool")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        key = read_key(sys.stdin)
        if args.action == "create":
            if not args.spool:
                raise BackupError("SPOOL_REQUIRED")
            result = create_backup(args.spool, args.archive, key)
            print(json.dumps({"action": "create", "verified": True,
                              "ciphertext_sha256": result["ciphertext_sha256"],
                              "plaintext_sha256": result["plaintext_sha256"]}, sort_keys=True))
        elif args.action == "verify":
            print(json.dumps({"action": "verify", **verify_backup(args.archive, key)}, sort_keys=True))
        else:
            if not args.output:
                raise BackupError("RESTORE_OUTPUT_REQUIRED")
            print(json.dumps({"action": "restore", **restore_backup(args.archive, args.output, key)}, sort_keys=True))
        return 0
    except BackupError as exc:
        print("ERROR=" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
