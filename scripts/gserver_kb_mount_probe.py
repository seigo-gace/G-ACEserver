#!/usr/bin/env python3
"""Bounded read-only F: / G-ACE-KB accessibility probe for WSL."""
from pathlib import Path
import os

F_MOUNT = Path("/mnt/f")
F_KB = F_MOUNT / "G-ACE-KB"


def mount_fs(mount, lines):
    """Match the exact mountpoint, never a parent or neighboring volume."""
    for line in lines:
        left, sep, right = line.partition(" - ")
        pieces, rest = left.split(), right.split()
        if sep and len(pieces) >= 5 and rest:
            name = pieces[4].replace("\\040", " ").replace("\\011", "\t")
            if name == str(mount):
                return rest[0]
    return None


def probe(mount=F_MOUNT, root=F_KB, mountinfo=None):
    mount, root = Path(mount), Path(root)
    if not mount.is_absolute() or root != mount / "G-ACE-KB":
        raise ValueError("INVALID_ROOT")
    if mount.is_symlink() or root.is_symlink():
        return {"state": "SYMLINK_REFUSED"}
    if not mount.exists():
        return {"state": "WSL_F_PATH_MISSING"}
    if not mount.is_dir():
        return {"state": "WSL_F_PATH_NOT_DIRECTORY"}
    if mountinfo is None:
        try:
            mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        except OSError:
            return {"state": "MOUNTINFO_UNREADABLE"}
    fs_type = mount_fs(mount, mountinfo)
    if fs_type is None or not os.path.ismount(mount):
        return {"state": "WSL_F_NOT_MOUNTED"}
    if not root.exists():
        return {"state": "F_MOUNTED_KB_ROOT_ABSENT", "filesystem": fs_type}
    if not root.is_dir():
        return {"state": "F_MOUNTED_KB_ROOT_NOT_DIRECTORY", "filesystem": fs_type}
    # Fixed known paths only, no directory traversal or reading document bytes.
    checks = {
        "KB_REPO_PRESENT": root.joinpath("repo").is_dir(),
        "KB_FORMAL_PRESENT": root.joinpath("data", "knowledge-records", "formal-kb.jsonl").is_file(),
        "KB_ACTIVE_MARKER_PRESENT": root.joinpath("data", "knowledge-records", "modulecatalog-reusable-active.json").is_file(),
        "KB_SEARCH_RECORDS_PRESENT": root.joinpath("data", "knowledge-search", "records").is_dir(),
    }
    return {"state": "F_KB_ROOT_READABLE", "filesystem": fs_type, **checks}


def main():
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=DEV_KB_F_MOUNT_READ_ONLY")
    try:
        result = probe()
        print("F_KB_MOUNT_STATE=" + result["state"])
        if "filesystem" in result:
            print("F_MOUNT_FILESYSTEM=" + result["filesystem"])
        for key in ("KB_REPO_PRESENT", "KB_FORMAL_PRESENT", "KB_ACTIVE_MARKER_PRESENT", "KB_SEARCH_RECORDS_PRESENT"):
            if key in result:
                print(key + "=" + str(result[key]))
        print("AUTO_MOUNT=False")
        print("F_SOURCE_MODIFIED=NONE")
        print("CHANGES=NONE")
        print("VERIFY=PASS")
    except (OSError, ValueError) as exc:
        print("F_KB_PROBE_ERROR_TYPE=" + type(exc).__name__)
        print("AUTO_MOUNT=False")
        print("CHANGES=NONE")
        print("VERIFY=FAIL")
        raise SystemExit(1)
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")


if __name__ == "__main__":
    main()
