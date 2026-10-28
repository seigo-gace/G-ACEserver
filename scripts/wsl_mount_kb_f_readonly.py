#!/usr/bin/env python3
"""Explicit one-session read-only DrvFs mount of the existing Windows F: KB.

Must run as WSL root by an intentional Master PowerShell command. Does not
modify Windows volumes, KB data, fstab, WSL automount, Docker, or services.
"""
import os
from pathlib import Path
import stat
import subprocess
import sys

TARGET = Path("/mnt/f")
KB = TARGET / "G-ACE-KB"
SOURCE = "F:"
MAX_WAIT_SECONDS = 25


class MountGateError(Exception):
    pass


def mounted_readonly(path):
    """Require an actual mountpoint and Linux read-only VFS flag."""
    return os.path.ismount(path) and bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def prepare_mountpoint(path=TARGET):
    """Return whether this call created the mountpoint (for safe rollback)."""
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or path.is_symlink():
        raise MountGateError("UNSAFE_MOUNT_PARENT_OR_SYMLINK")
    if path.exists():
        if not path.is_dir():
            raise MountGateError("MOUNTPOINT_NOT_DIRECTORY")
        if os.path.ismount(path):
            if not mounted_readonly(path):
                raise MountGateError("EXISTING_MOUNT_NOT_READ_ONLY")
            return False
        if any(path.iterdir()):
            raise MountGateError("NONEMPTY_UNMOUNTED_MOUNTPOINT")
        return False
    path.mkdir(mode=0o755)
    return True


def attach(mount=TARGET, kb=KB, runner=subprocess.run):
    """Only one F: -> /mnt/f read-only mount, no fallback to read-write."""
    if mount != TARGET or kb != KB:
        raise MountGateError("MOUNT_PATH_NOT_APPROVED")
    if os.geteuid() != 0:
        raise MountGateError("WSL_ROOT_REQUIRED")
    created = False
    mounted_by_us = False
    try:
        created = prepare_mountpoint(mount)
        if not os.path.ismount(mount):
            try:
                done = runner(
                    ["mount", "-t", "drvfs", "-o", "ro", SOURCE, str(mount)],
                    check=False, capture_output=True, timeout=MAX_WAIT_SECONDS
                )
            except subprocess.TimeoutExpired:
                raise MountGateError("READ_ONLY_MOUNT_TIMEOUT") from None
            if done.returncode != 0:
                raise MountGateError("READ_ONLY_DRVFS_MOUNT_FAILED")
            mounted_by_us = True
        if not mounted_readonly(mount):
            raise MountGateError("MOUNT_READ_ONLY_NOT_PROVEN")
        if kb.is_symlink() or not kb.is_dir():
            raise MountGateError("WINDOWS_KB_ROOT_NOT_VISIBLE")
        return "MOUNTED_READ_ONLY_VERIFIED"
    except BaseException:
        # Never leave a newly mounted F: drive exposed as read-write or with
        # an inaccessible KB. Do not touch a preexisting mount or user files.
        if mounted_by_us:
            try:
                subprocess.run(["umount", str(mount)], check=False,
                               capture_output=True, timeout=MAX_WAIT_SECONDS)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if created and not os.path.ismount(mount):
            try:
                mount.rmdir()
            except OSError:
                pass
        raise


def main():
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=DEV_KB_F_DRVFS_READ_ONLY_ATTACH_EXPLICIT")
    try:
        result = attach()
        print("F_WSL_MOUNT=" + result)
        print("KB_F_ROOT_VISIBLE=True")
        print("F_WINDOWS_CONTENTS_CHANGED=NONE")
        print("FSTAB_CHANGED=False")
        print("WSL_AUTOMOUNT_CHANGED=False")
        print("CHANGES=WSL_SESSION_READ_ONLY_MOUNT_ONLY")
        print("VERIFY=PASS")
        return 0
    except (MountGateError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, MountGateError) else type(error).__name__
        print("MOUNT_GATE_ERROR=" + code)
        print("F_WINDOWS_CONTENTS_CHANGED=NONE")
        print("FSTAB_CHANGED=False")
        print("WSL_AUTOMOUNT_CHANGED=False")
        print("VERIFY=FAIL")
        return 1
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")


if __name__ == "__main__":
    sys.exit(main())
