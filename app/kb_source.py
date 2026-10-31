"""Read-only Gserver adapter for the existing G-ACE Dev KB Current authority.

No search engine, no index creation, no KB receiver, no network or filesystem writes.
The authoritative KB implementation remains seigo-gace/gace-dev-kb.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

F_ROOT = Path("/mnt/f/G-ACE-KB")
MAX_AUTH_JSON = 256 * 1024
MAX_HASH_FILE = 2 * 1024 ** 3
SHA = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")

MARKER = ("data", "knowledge-records", "modulecatalog-reusable-active.json")
CURRENT = ("data", "knowledge-sources", "accepted", "modulecatalog-reusable-current")
INTAKE = ("data", "knowledge-intake", "modulecatalog")
AUTH_HASHES = {
    "formalKbSha256": ("data", "knowledge-records", "formal-kb.jsonl"),
    "knowledgeRecordsSha256": CURRENT + ("knowledge-records.jsonl",),
    "knowledgeMetadataSha256": CURRENT + ("knowledge-metadata.jsonl",),
    "relationshipsSha256": CURRENT + ("relationships.jsonl",),
    "casesSha256": CURRENT + ("cases.jsonl",),
    "deliveryManifestSha256": CURRENT + ("delivery-manifest.json",),
}


class KBSourceError(Exception):
    pass


def _path(root, *parts):
    current = root
    if not root.is_absolute() or root.is_symlink():
        raise KBSourceError("KB_ROOT_INVALID")
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise KBSourceError("KB_SYMLINK_REFUSED")
    return current


def _is_dir(root, *parts):
    candidate = _path(root, *parts)
    return candidate.is_dir()


def _is_file(root, *parts):
    candidate = _path(root, *parts)
    return candidate.is_file()


def _open_regular(root, parts):
    path = _path(root, *parts)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise KBSourceError("KB_FILE_TYPE_UNSAFE")
    return fd, info.st_size


def _read_json(root, parts):
    fd, size = _open_regular(root, parts)
    try:
        if size > MAX_AUTH_JSON:
            raise KBSourceError("KB_AUTH_JSON_TOO_LARGE")
        data = bytearray()
        while len(data) <= MAX_AUTH_JSON:
            chunk = os.read(fd, min(65536, MAX_AUTH_JSON + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > MAX_AUTH_JSON:
            raise KBSourceError("KB_AUTH_JSON_TOO_LARGE")
        try:
            result = json.loads(data)
        except (UnicodeError, json.JSONDecodeError):
            raise KBSourceError("KB_AUTH_JSON_INVALID") from None
        if not isinstance(result, dict):
            raise KBSourceError("KB_AUTH_JSON_INVALID")
        return result
    finally:
        os.close(fd)


def _sha256(root, parts):
    fd, size = _open_regular(root, parts)
    try:
        if size > MAX_HASH_FILE:
            raise KBSourceError("KB_HASH_FILE_TOO_LARGE")
        actual = hashlib.sha256()
        seen = 0
        while True:
            buf = os.read(fd, 1024 * 1024)
            if not buf:
                break
            seen += len(buf)
            if seen > MAX_HASH_FILE:
                raise KBSourceError("KB_HASH_FILE_TOO_LARGE")
            actual.update(buf)
        if seen != size:
            raise KBSourceError("KB_FILE_CHANGED")
        return actual.hexdigest()
    finally:
        os.close(fd)


def inspect(root=F_ROOT, *, verify_hashes=False, enforce_mount=True):
    root = Path(root)
    if not root.is_absolute() or root.is_symlink():
        raise KBSourceError("KB_ROOT_INVALID")
    if root == F_ROOT and enforce_mount and not os.path.ismount("/mnt/f"):
        raise KBSourceError("KB_F_MOUNT_UNAVAILABLE")
    if not root.is_dir():
        raise KBSourceError("KB_ROOT_NOT_PRESENT")
    # These are three independent facts; a historical formal corpus is NOT
    # evidence that the generalized ModuleCatalog Current was activated.
    baseline = _is_file(root, "data", "knowledge-records", "formal-kb.jsonl")
    corpus = _is_dir(root, "data", "knowledge-search", "records")
    kb_repo = _is_file(root, "repo", "scripts", "check-modulecatalog-kb-runtime-windows.ps1")
    runtime_exe = _is_file(root, "runtime", "mcp-vector-search", "Scripts", "mcp-vector-search.exe")

    marker_present = _is_file(root, *MARKER)
    journal = _path(root, *INTAKE, "activation-transaction.json")
    if journal.exists() or journal.is_symlink():
        raise KBSourceError("KB_ACTIVATION_TRANSACTION_UNRESOLVED")
    if not marker_present:
        return {
            "current": "NOT_ACTIVATED_OR_NOT_FOUND",
            "historical_formal_corpus_present": baseline,
            "search_corpus_present": corpus,
            "existing_kb_source_present": kb_repo,
            "existing_windows_mvs_present": runtime_exe,
            "kb_search_verified": False,
            "changes": "NONE",
        }
    marker = _read_json(root, MARKER)
    commit = marker.get("catalogCommit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise KBSourceError("KB_CATALOG_COMMIT_INVALID")
    state = _read_json(root, CURRENT + ("runtime-state.json",))
    receipt = _read_json(root, INTAKE + ("receipts", commit + ".json"))
    for item in (marker, state, receipt):
        if item.get("status") != "ACTIVE":
            raise KBSourceError("KB_AUTHORITY_NOT_ACTIVE")
        if item.get("catalogCommit") != commit:
            raise KBSourceError("KB_AUTHORITY_COMMIT_MISMATCH")
        if type(item.get("projectionSchemaVersion")) is not int or item["projectionSchemaVersion"] != 2:
            raise KBSourceError("KB_AUTHORITY_SCHEMA_INVALID")
    for key, parts in AUTH_HASHES.items():
        expected = marker.get(key)
        if not isinstance(expected, str) or not SHA.fullmatch(expected):
            raise KBSourceError("KB_AUTHORITY_HASH_INVALID")
        if any(item.get(key) != expected for item in (state, receipt)):
            raise KBSourceError("KB_AUTHORITY_HASH_DISAGREEMENT")
        if verify_hashes and _sha256(root, parts).lower() != expected.lower():
            raise KBSourceError("KB_CURRENT_FILE_HASH_MISMATCH")
    counts = {}
    for key in ("totalFormalRecordCount", "knowledgeUnitCount", "relationshipCount", "caseCount"):
        value = marker.get(key)
        if type(value) is not int or value < 0 or value > 100000000:
            raise KBSourceError("KB_AUTHORITY_COUNT_INVALID")
        counts[key] = value
    if counts["totalFormalRecordCount"] < counts["knowledgeUnitCount"]:
        raise KBSourceError("KB_FORMAL_COUNT_INVALID")
    if not baseline or not corpus or not kb_repo:
        raise KBSourceError("KB_RUNTIME_DEPENDENCY_MISSING")
    # Fail closed if an activation changed while we were reading the Current.
    if journal.exists() or _read_json(root, MARKER) != marker or _read_json(root, CURRENT + ("runtime-state.json",)) != state or _read_json(root, INTAKE + ("receipts", commit + ".json")) != receipt:
        raise KBSourceError("KB_CURRENT_CHANGED_DURING_INSPECTION")
    return {
        "current": "ACTIVE_AUTHORITY_HASHED" if verify_hashes else "ACTIVE_AUTHORITY_CONSISTENT",
        "catalog_commit": commit,
        "counts": counts,
        "historical_formal_corpus_present": baseline,
        "search_corpus_present": corpus,
        "existing_kb_source_present": kb_repo,
        "existing_windows_mvs_present": runtime_exe,
        "kb_search_verified": False,
        "kb_mcp_deep_verified": False,
        "kb_runtime_projection_verified": False,
        "changes": "NONE",
    }


def verify_existing_projection(root, authority, *, timeout_seconds=180):
    """Reuse the installed Dev KB's actual byte-exact projection verifier.

    This invokes only the existing read-only Python verifier. It never runs
    index/activation/receiver, writes a manifest, or starts a scheduled service.
    """
    if authority.get("current") != "ACTIVE_AUTHORITY_HASHED":
        raise KBSourceError("KB_PROJECTION_REQUIRES_HASHED_ACTIVE")
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 300:
        raise KBSourceError("KB_PROJECTION_TIMEOUT_INVALID")
    commit = authority["catalog_commit"]
    count = authority["counts"]["knowledgeUnitCount"]
    if not count:
        raise KBSourceError("KB_PROJECTION_COUNT_EMPTY")
    script = _path(root, "repo", "scripts", "verify_modulecatalog_runtime_projection.py")
    if not script.is_file():
        raise KBSourceError("KB_EXISTING_VERIFIER_MISSING")
    source_corpus = _path(root, *CURRENT, "records")
    active_corpus = _path(root, "data", "knowledge-search", "records")
    if not source_corpus.is_dir() or not active_corpus.is_dir():
        raise KBSourceError("KB_PROJECTION_CORPUS_MISSING")
    prefix = "accepted-modulecatalog-reusable-" + commit[:12] + "-"
    command = [sys.executable, "-B", str(script), "--source-corpus", str(source_corpus),
               "--runtime-corpus", str(active_corpus), "--prefix", prefix,
               "--expected-count", str(count)]
    try:
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        raise KBSourceError("KB_PROJECTION_VERIFIER_TIMEOUT") from None
    if run.returncode != 0 or "GACE_MODULECATALOG_RUNTIME_PROJECTION=PASS" not in run.stdout:
        raise KBSourceError("KB_EXISTING_PROJECTION_VERIFIER_FAILED")
    # Revalidate Current after the subprocess; a change invalidates the result.
    current = inspect(root, verify_hashes=True, enforce_mount=False)
    if current.get("catalog_commit") != commit or current.get("counts") != authority["counts"]:
        raise KBSourceError("KB_CURRENT_CHANGED_AFTER_PROJECTION")
    return {"projection": "EXISTING_KB_VERIFIER_PASS", "search_mcp_verified": False,
            "changes": "NONE"}


def verify_existing_counts(root, authority):
    """Independently count the actual Current JSONL rows, with bounded reads.

    This never reindexes or changes the KB. Marker-declared counts alone
    are not proof that the same numbers of KB records exist on the drive.
    """
    if authority.get("current") != "ACTIVE_AUTHORITY_HASHED":
        raise KBSourceError("KB_COUNTS_REQUIRE_HASHED_ACTIVE")
    root = Path(root)
    declared = authority["counts"]
    source_checks = (
        ("formal_records", AUTH_HASHES["formalKbSha256"], "totalFormalRecordCount"),
        ("reusable_records", AUTH_HASHES["knowledgeRecordsSha256"], "knowledgeUnitCount"),
        ("metadata", AUTH_HASHES["knowledgeMetadataSha256"], "knowledgeUnitCount"),
        ("relationships", AUTH_HASHES["relationshipsSha256"], "relationshipCount"),
        ("cases", AUTH_HASHES["casesSha256"], "caseCount"),
    )
    counts = {}
    for label, parts, field in source_checks:
        fd, size = _open_regular(root, parts)
        try:
            if size > MAX_HASH_FILE:
                raise KBSourceError("KB_COUNT_FILE_TOO_LARGE")
            pending = b""
            total = 0
            read = 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if read > MAX_HASH_FILE:
                    raise KBSourceError("KB_COUNT_FILE_TOO_LARGE")
                pending += chunk
                lines = pending.split(b"\n")
                pending = lines.pop()
                total += sum(bool(line.strip()) for line in lines)
                if len(pending) > 8 * 1024 * 1024:
                    raise KBSourceError("KB_JSONL_RECORD_TOO_LARGE")
            if pending.strip():
                total += 1
            if read != size:
                raise KBSourceError("KB_COUNT_FILE_CHANGED")
            if total != declared[field]:
                raise KBSourceError("KB_CURRENT_COUNT_MISMATCH_" + label.upper())
            counts[label] = total
        finally:
            os.close(fd)
    # A count is only valid for the Current we initially inspected.
    refreshed = inspect(root, verify_hashes=True, enforce_mount=False)
    if refreshed.get("catalog_commit") != authority.get("catalog_commit") or refreshed.get("counts") != declared:
        raise KBSourceError("KB_CURRENT_CHANGED_DURING_COUNT")
    return {"counts": counts, "verified": True, "changes": "NONE"}
