#!/usr/bin/env python3
"""Single-user Gserver file transfer via the existing G: mount (never overwrites)."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from storage import Storage, InvalidPath, StorageUnavailable, components
from storage_mutations import digest, quota, to_trash, restore as restore_trashed, trash_list, trash_info, replace_version

DRIVE = Path("/mnt/g")
FILES = DRIVE / "GserverStorage" / "files"
CHUNK = 1024 * 1024
DEFAULT_RESERVE_BYTES = 64 * 1024 * 1024


def checked_name(name):
    parts = components(name)
    if len(parts) != 1:
        raise InvalidPath()
    return parts[0]


def open_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise InvalidPath()
    return fd


def _sync_directory(fd):
    try:
        os.fsync(fd)
    except OSError as exc:
        if exc.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
            raise


def save_new(source_fd, parent_fd, name):
    """Copy bounded-memory, fsync and publish without overwriting an existing file."""
    name = checked_name(name)
    initial = os.fstat(source_fd)
    if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
        raise InvalidPath()
    partial = ".gserver-part-" + secrets.token_hex(16)
    dest_fd = None
    digest = hashlib.sha256()
    total = 0
    published = False
    try:
        dest_fd = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        while True:
            data = os.read(source_fd, CHUNK)
            if not data:
                break
            view = memoryview(data)
            while view:
                written = os.write(dest_fd, view)
                if written <= 0:
                    raise OSError(errno.EIO, "incomplete write")
                view = view[written:]
            total += len(data)
            digest.update(data)
        after = os.fstat(source_fd)
        if total != initial.st_size or after.st_size != initial.st_size or after.st_mtime_ns != initial.st_mtime_ns:
            raise ValueError("source changed during transfer")
        os.fsync(dest_fd)
        os.close(dest_fd)
        dest_fd = None
        # The link fails with EEXIST even for a symlink or directory: no replace.
        os.link(partial, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
        published = True
        _sync_directory(parent_fd)
        return {"name": name, "bytes": total, "sha256": digest.hexdigest()}
    finally:
        if dest_fd is not None:
            os.close(dest_fd)
        try:
            os.unlink(partial, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        if published:
            _sync_directory(parent_fd)


def storage(mount=None, root=None):
    mount = DRIVE if mount is None else mount
    root = FILES if root is None else root
    if not os.path.ismount(mount):
        raise StorageUnavailable()
    return Storage(str(mount), str(root))


def _check_budget(store, source_bytes, max_bytes, reserve_bytes):
    if max_bytes is not None and (max_bytes < 0 or source_bytes > max_bytes):
        raise ValueError("source exceeds --max-bytes")
    if reserve_bytes < 0:
        raise ValueError("negative --reserve-bytes")
    available = quota(store)["available_bytes"]
    if available < source_bytes + reserve_bytes:
        raise OSError(errno.ENOSPC, "not enough G: space with reserved headroom")


def put(source, mount=None, root=None, *, max_bytes=None, reserve_bytes=DEFAULT_RESERVE_BYTES):
    store = storage(mount, root)
    fd = open_regular(source)
    try:
        _check_budget(store, os.fstat(fd).st_size, max_bytes, reserve_bytes)
        with store.directory() as folder:
            return save_new(fd, folder, checked_name(Path(source).name))
    finally:
        os.close(fd)


def get(name, dest_dir, mount=None, root=None):
    store = storage(mount, root)
    name = checked_name(name)
    target = Path(dest_dir).expanduser()
    with store.open_file(name) as (src, size, _):
        directory = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            result = save_new(src, directory, name)
            if result["bytes"] != size:
                raise ValueError("source changed during copy")
            return result
        finally:
            os.close(directory)


def list_files(mount=None, root=None):
    return storage(mount, root).listing(limit=200)


def main():
    parser = argparse.ArgumentParser(description="Gserver owner-only G: file CLI; never exposes a new HTTP write API")
    group = parser.add_subparsers(dest="action", required=True)
    p = group.add_parser("put", help="Copy a local file to G:; refuse overwrites")
    p.add_argument("source")
    p.add_argument("--max-bytes", type=int, default=None)
    p.add_argument("--reserve-bytes", type=int, default=DEFAULT_RESERVE_BYTES)
    g = group.add_parser("get", help="Copy one stored file into a local directory")
    g.add_argument("name")
    g.add_argument("into_directory")
    group.add_parser("list", help="Show up to 200 stored files")
    group.add_parser("quota", help="Show available bytes on mounted G: without writes")
    h = group.add_parser("hash", help="Calculate sha256 before a guarded mutation")
    h.add_argument("name")
    z = group.add_parser("trash", help="Recoverably hide a file; require current sha256")
    z.add_argument("name")
    z.add_argument("--expect-sha256", required=True)
    group.add_parser("trash-list", help="List up to 100 opaque recovery ids, without reading large video files")
    info = group.add_parser("trash-info", help="Calculate sha256 for one recovery id")
    info.add_argument("restore_id")
    r = group.add_parser("restore", help="Restore an old version without overwriting existing files")
    r.add_argument("restore_id")
    r.add_argument("name")
    r.add_argument("--expect-sha256", required=True)
    v = group.add_parser("replace", help="Atomically replace file and preserve the old version")
    v.add_argument("source")
    v.add_argument("name")
    v.add_argument("--expect-sha256", required=True)
    v.add_argument("--max-bytes", type=int, default=None)
    v.add_argument("--reserve-bytes", type=int, default=DEFAULT_RESERVE_BYTES)
    args = parser.parse_args()
    if args.action == "put":
        result = put(args.source, max_bytes=args.max_bytes, reserve_bytes=args.reserve_bytes)
    elif args.action == "get":
        result = get(args.name, args.into_directory)
    elif args.action == "list":
        result = list_files()
    else:
        store = storage()
        if args.action == "quota":
            result = quota(store)
        elif args.action == "hash":
            result = digest(store, args.name)
        elif args.action == "trash":
            result = to_trash(store, args.name, args.expect_sha256)
        elif args.action == "trash-list":
            result = trash_list(store)
        elif args.action == "trash-info":
            result = trash_info(store, args.restore_id)
        elif args.action == "restore":
            result = restore_trashed(store, args.restore_id, args.name, args.expect_sha256)
        elif args.action == "replace":
            source_fd = open_regular(args.source)
            try:
                result = replace_version(store, args.name, source_fd, args.expect_sha256,
                                         max_bytes=args.max_bytes, reserve_bytes=args.reserve_bytes)
            finally:
                os.close(source_fd)
        else:
            raise RuntimeError("unknown action")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (InvalidPath, StorageUnavailable, FileExistsError, FileNotFoundError,
            PermissionError, ValueError, OSError) as error:
        print("GSERVER_TRANSFER_FAILED=" + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
