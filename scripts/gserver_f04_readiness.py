#!/usr/bin/env python3
"""Read-only F04 bridge readiness: F: mount probe plus KB Current authority inspect."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

from gserver_kb_mount_probe import probe
from kb_source import inspect, KBSourceError, F_ROOT


def audit(*, verify_hashes=False):
    mount = probe()
    kb = None
    kb_error = None
    if mount.get("state") == "F_KB_ROOT_READABLE":
        try:
            kb = inspect(F_ROOT, verify_hashes=verify_hashes, enforce_mount=True)
        except KBSourceError as exc:
            kb_error = type(exc).__name__
    current = (kb or {}).get("current", "NOT_INSPECTED")
    partial = mount.get("state") == "F_KB_ROOT_READABLE" and kb is not None and kb_error is None
    return {
        "scope": "f04_dev_kb_read_only_readiness",
        "mount": mount,
        "kb_current": current,
        "kb_authority": kb,
        "kb_error": kb_error,
        "kb_search_e2e": "NOT_VERIFIED",
        "f04_bridge_readiness": "PASS" if partial else "NOT_VERIFIED",
    }


def main():
    verify_hashes = "--verify-hashes" in sys.argv[1:]
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=DEV_KB_F04_READINESS_READ_ONLY")
    exit_code = 1
    try:
        payload = audit(verify_hashes=verify_hashes)
        print("F_KB_MOUNT_STATE=" + payload["mount"].get("state", "UNKNOWN"))
        print("KB_CURRENT=" + payload["kb_current"])
        if payload["kb_error"]:
            print("KB_INSPECT_ERROR=" + payload["kb_error"])
        print("KB_SEARCH_E2E=" + payload["kb_search_e2e"])
        print("F04_BRIDGE_READINESS=" + payload["f04_bridge_readiness"])
        safe = {
            "mount_state": payload["mount"].get("state"),
            "kb_current": payload["kb_current"],
            "kb_error": payload["kb_error"],
            "kb_search_e2e": payload["kb_search_e2e"],
            "f04_bridge_readiness": payload["f04_bridge_readiness"],
        }
        if payload["kb_authority"]:
            auth = payload["kb_authority"]
            safe["existing_kb_source_present"] = auth.get("existing_kb_source_present")
            safe["search_corpus_present"] = auth.get("search_corpus_present")
        print("AUDIT_JSON=" + json.dumps(safe, separators=(",", ":"), sort_keys=True))
        print("F_SOURCE_MODIFIED=NONE")
        print("CHANGES=NONE")
        exit_code = 0 if payload["f04_bridge_readiness"] == "PASS" else 1
        print("VERIFY=" + ("PASS" if exit_code == 0 else "FAIL"))
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
