"""Owner-only recoverable storage operations on the existing G: subtree.

No remote upload endpoint, bulk delete, in-place replace, or background worker.
"""
import hashlib
import os
import secrets
import stat

from storage import InvalidPath, StorageUnavailable, components

TRASH = '.gserver-trash'
CHUNK = 1024 * 1024


def checked_file(name):
    parts = components(name)
    if len(parts) != 1:
        raise InvalidPath()
    return parts[0]


def _check_metadata(fd, root_dev):
    s = os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_dev != root_dev:
        raise InvalidPath()
    return s


def _hash_fd(fd):
    digest = hashlib.sha256()
    total = 0
    while True:
        data = os.read(fd, CHUNK)
        if not data:
            break
        digest.update(data)
        total += len(data)
    return digest.hexdigest(), total


def _verify(expected):
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('expected sha256 must be lowercase hex digest')
    return expected


def _fsync_dir(fd):
    try:
        os.fsync(fd)
    except OSError as error:
        # NTFS-over-DrvFS and some host directory descriptors reject fsync.
        if error.errno not in (22, 95, 9):
            raise


def _trash_dir(parent_fd, *, create):
    if create:
        try:
            os.mkdir(TRASH, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
    fd = os.open(TRASH, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    if os.fstat(fd).st_dev != os.fstat(parent_fd).st_dev:
        os.close(fd)
        raise InvalidPath()
    return fd


def digest(store, name):
    checked_file(name)
    with store.open_file(name) as (fd, length, _):
        sha, count = _hash_fd(fd)
        if count != length:
            raise ValueError('file changed while hashing')
        return {'name': name, 'bytes': count, 'sha256': sha}


def quota(store):
    with store.directory() as root:
        s = os.fstatvfs(root)
        return {'total_bytes': s.f_blocks * s.f_frsize,
                'available_bytes': s.f_bavail * s.f_frsize,
                'block_size': s.f_frsize}


def to_trash(store, name, expected_sha256):
    """Link old bytes to private trash first, then remove visible name.

    If interrupted between those steps, the original survives at least once.
    """
    name = checked_file(name)
    expected_sha256 = _verify(expected_sha256)
    with store.directory() as folder:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        try:
            original = _check_metadata(fd, os.fstat(folder).st_dev)
            calculated, count = _hash_fd(fd)
            after = os.fstat(fd)
            if count != original.st_size or (after.st_size, after.st_mtime_ns) != (original.st_size, original.st_mtime_ns):
                raise ValueError('file changed during validation')
            if calculated != expected_sha256:
                raise ValueError('hash mismatch: refusing delete')
            trash_fd = _trash_dir(folder, create=True)
            linked = False
            removed = False
            token = secrets.token_hex(16)
            try:
                # os.link fails rather than replacing an existing trash token.
                os.link(name, token, src_dir_fd=folder, dst_dir_fd=trash_fd, follow_symlinks=False)
                linked = True
                saved = os.stat(token, dir_fd=trash_fd, follow_symlinks=False)
                current = os.stat(name, dir_fd=folder, follow_symlinks=False)
                if (saved.st_dev, saved.st_ino) != (original.st_dev, original.st_ino) or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                    raise ValueError('source changed while moving to trash')
                _fsync_dir(trash_fd)
                os.unlink(name, dir_fd=folder)
                removed = True
                _fsync_dir(folder)
                return {'trashed': name, 'restore_id': token, 'bytes': count, 'sha256': calculated}
            finally:
                # If original name still exists, drop our temporary duplicate.
                # If original was removed, retain backup even on fsync failure.
                if linked and not removed:
                    os.unlink(token, dir_fd=trash_fd)
                os.close(trash_fd)
        finally:
            os.close(fd)


def restore(store, token, name, expected_sha256):
    name = checked_file(name)
    if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise InvalidPath()
    expected_sha256 = _verify(expected_sha256)
    with store.directory() as folder:
        trash_fd = _trash_dir(folder, create=False)
        try:
            fd = os.open(token, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=trash_fd)
            try:
                info = _check_metadata(fd, os.fstat(folder).st_dev)
                sha, size = _hash_fd(fd)
                if size != info.st_size or sha != expected_sha256:
                    raise ValueError('trash item changed / expected hash mismatch')
                os.link(token, name, src_dir_fd=trash_fd, dst_dir_fd=folder, follow_symlinks=False)
                _fsync_dir(folder)
                os.unlink(token, dir_fd=trash_fd)
                _fsync_dir(trash_fd)
                return {'restored': name, 'bytes': size, 'sha256': sha}
            finally:
                os.close(fd)
        finally:
            os.close(trash_fd)


def trash_list(store, limit=100):
    """List opaque recovery IDs; user can obtain digest for restoring a lost receipt."""
    if not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError('invalid trash list limit')
    with store.directory() as folder:
        try:
            trash_fd = _trash_dir(folder, create=False)
        except FileNotFoundError:
            return {'entries': [], 'truncated': False}
        try:
            tokens = []
            with os.scandir(trash_fd) as entries:
                for index, item in enumerate(entries):
                    if index >= 10000:
                        raise StorageUnavailable()
                    if len(item.name) != 32 or any(c not in '0123456789abcdef' for c in item.name):
                        continue
                    info = item.stat(follow_symlinks=False)
                    if stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_dev == os.fstat(folder).st_dev:
                        tokens.append((item.name, info.st_size))
            tokens.sort()
            items = []
            for token, size in tokens[:limit]:
                items.append({'restore_id': token, 'bytes': size})
            return {'entries': items, 'truncated': len(tokens) > limit}
        finally:
            os.close(trash_fd)


def trash_info(store, token):
    if not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise InvalidPath()
    with store.directory() as folder:
        trash_fd = _trash_dir(folder, create=False)
        try:
            fd = os.open(token, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=trash_fd)
            try:
                info = _check_metadata(fd, os.fstat(folder).st_dev)
                sha, size = _hash_fd(fd)
                after = os.fstat(fd)
                if size != info.st_size or (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                    raise ValueError('trash item changed during hashing')
                return {'restore_id': token, 'bytes': size, 'sha256': sha}
            finally:
                os.close(fd)
        finally:
            os.close(trash_fd)


def _copy_new_version(source_fd, parent_fd, stage, size, max_bytes, reserve_bytes):
    if max_bytes is not None and (not isinstance(max_bytes, int) or max_bytes < 0 or size > max_bytes):
        raise ValueError('source exceeds --max-bytes')
    if not isinstance(reserve_bytes, int) or reserve_bytes < 0:
        raise ValueError('invalid reserve bytes')
    usage = os.fstatvfs(parent_fd)
    available = usage.f_bavail * usage.f_frsize
    if available < size + reserve_bytes:
        raise OSError(28, 'insufficient free storage with reserved headroom')
    output = os.open(stage, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    try:
        digest_value = hashlib.sha256()
        count = 0
        while True:
            chunk = os.read(source_fd, CHUNK)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                amount = os.write(output, view)
                if amount <= 0:
                    raise OSError(5, 'incomplete write')
                view = view[amount:]
            digest_value.update(chunk)
            count += len(chunk)
        if count != size:
            raise ValueError('source changed during copy')
        os.fsync(output)
        return count, digest_value.hexdigest()
    finally:
        os.close(output)


def replace_version(store, name, source_fd, expected_sha256, *, max_bytes=None, reserve_bytes=64 * 1024 * 1024):
    """Atomic target replacement with recoverable old version and explicit digest guard.

    A crash before replace leaves old name active; after replace it leaves old bytes
    in private trash. Never overwrite if the expected old SHA doesn't match.
    """
    name = checked_file(name)
    expected_sha256 = _verify(expected_sha256)
    initial = os.fstat(source_fd)
    if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
        raise InvalidPath()
    with store.directory() as folder:
        current_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
        try:
            old = _check_metadata(current_fd, os.fstat(folder).st_dev)
            old_sha, old_length = _hash_fd(current_fd)
            if old_length != old.st_size or old_sha != expected_sha256:
                raise ValueError('current version does not match --expect-sha256')
            stage = '.gserver-part-' + secrets.token_hex(16)
            token = secrets.token_hex(16)
            committed = False
            backed_up = False
            try:
                count, new_sha = _copy_new_version(source_fd, folder, stage, initial.st_size, max_bytes, reserve_bytes)
                after = os.fstat(source_fd)
                if (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                    raise ValueError('source changed during versioned replacement')
                trash_fd = _trash_dir(folder, create=True)
                try:
                    now = os.stat(name, dir_fd=folder, follow_symlinks=False)
                    if (now.st_dev, now.st_ino, now.st_size, now.st_mtime_ns, now.st_nlink) != (old.st_dev, old.st_ino, old.st_size, old.st_mtime_ns, old.st_nlink):
                        raise ValueError('target changed during replacement')
                    os.link(name, token, src_dir_fd=folder, dst_dir_fd=trash_fd, follow_symlinks=False)
                    backed_up = True
                    saved = os.stat(token, dir_fd=trash_fd, follow_symlinks=False)
                    if (saved.st_dev, saved.st_ino) != (old.st_dev, old.st_ino):
                        raise ValueError('backup inode differs')
                    _fsync_dir(trash_fd)
                    os.replace(stage, name, src_dir_fd=folder, dst_dir_fd=folder)
                    committed = True
                    _fsync_dir(folder)
                    return {'replaced': name, 'bytes': count, 'sha256': new_sha,
                            'old_version_id': token, 'old_sha256': old_sha}
                finally:
                    if backed_up and not committed:
                        # Undo only our new backup link, never delete the original.
                        os.unlink(token, dir_fd=trash_fd)
                    os.close(trash_fd)
            finally:
                if not committed:
                    try:
                        os.unlink(stage, dir_fd=folder)
                    except FileNotFoundError:
                        pass
        finally:
            os.close(current_fd)
