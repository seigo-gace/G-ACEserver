#!/usr/bin/env python3
"""Read-only F03 G: mount and quota snapshot; no writes or disconnect simulation."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from storage import Storage, StorageUnavailable
from storage_mutations import quota

G_MOUNT = Path("/mnt/g")
FILES = G_MOUNT / "GserverStorage" / "files"


def mount_fingerprint(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return {"st_dev": stat.st_dev, "st_ino": stat.st_ino}


def audit():
    mounted = os.path.ismount(G_MOUNT)
    subtree = FILES.is_dir()
    quota_info = None
    quota_state = "NOT_AVAILABLE"
    if mounted and subtree:
        store = Storage(G_MOUNT, FILES)
        try:
            quota_info = quota(store)
            quota_state = "OK"
        except (StorageUnavailable, OSError):
            quota_state = "UNAVAILABLE"
    partial = mounted and subtree and quota_state == "OK"
    return {
        "scope": "f03_storage_mount_read_only",
        "g_mounted": mounted,
        "files_subtree_present": subtree,
        "authorized_subtree_only": str(FILES) != str(G_MOUNT),
        "mount_fingerprint": mount_fingerprint(G_MOUNT) if mounted else None,
        "quota_state": quota_state,
        "quota": quota_info,
        "usb_disconnect_test": "NOT_RUN",
        "capacity_exhaustion_test": "NOT_RUN",
        "f03_mount_readiness": "PASS" if partial else "NOT_VERIFIED",
    }


def main():
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=F03_STORAGE_MOUNT_READ_ONLY_AUDIT")
    exit_code = 1
    try:
        payload = audit()
        print("G_MOUNTED=" + str(payload["g_mounted"]))
        print("FILES_SUBTREE_PRESENT=" + str(payload["files_subtree_present"]))
        print("QUOTA_STATE=" + payload["quota_state"])
        print("USB_DISCONNECT_TEST=" + payload["usb_disconnect_test"])
        print("F03_MOUNT_READINESS=" + payload["f03_mount_readiness"])
        print(
            "AUDIT_JSON="
            + json.dumps(
                {key: value for key, value in payload.items() if key != "scope"},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        print("CHANGES=NONE")
        exit_code = 0 if payload["f03_mount_readiness"] == "PASS" else 1
        print("VERIFY=" + ("PASS" if exit_code == 0 else "FAIL"))
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
