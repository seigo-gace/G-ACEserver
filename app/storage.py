"""Read-only storage capability scoped to an explicitly configured mounted subtree."""
from contextlib import contextmanager
import hashlib
import heapq
import os
from pathlib import Path
import stat
import threading


class StorageUnavailable(Exception):
    pass


class InvalidPath(Exception):
    pass


def components(value):
    if not isinstance(value, str) or len(value) > 4096 or '\\' in value or '\0' in value:
        raise InvalidPath()
    if value == '':
        return []
    parts = value.split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{prefix}{n}' for prefix in ('COM', 'LPT') for n in range(1, 10)}
    if any(p in ('', '.', '..') or len(p.encode()) > 255 or p.endswith(('.', ' '))
           or ':' in p or any(ord(c) < 32 for c in p)
           or p.split('.')[0].upper() in reserved for p in parts):
        raise InvalidPath()
    return parts


def byte_range(value, size):
    if value is None:
        return 0, size
    if not value.startswith('bytes=') or ',' in value:
        raise ValueError('invalid range')
    fields = value[6:].split('-')
    if len(fields) != 2 or size == 0:
        raise ValueError('unsatisfiable range')
    start, end = fields
    if (start and not start.isascii()) or (end and not end.isascii()):
        raise ValueError('invalid range')
    if not start:
        if not end.isdigit() or int(end) <= 0:
            raise ValueError('invalid range')
        return max(0, size - int(end)), size
    if not start.isdigit() or (end and not end.isdigit()):
        raise ValueError('invalid range')
    start = int(start)
    stop = min(size, int(end) + 1) if end else size
    if start >= size or stop <= start:
        raise ValueError('unsatisfiable range')
    return start, stop


class Storage:
    def __init__(self, mount, root):
        self.mount = Path(mount)
        self.root = Path(root)
        if not self.mount.is_absolute() or not self.root.is_absolute():
            raise InvalidPath()
        try:
            relative = self.root.relative_to(self.mount).as_posix()
        except ValueError:
            raise InvalidPath() from None
        self.prefix = components(relative)
        if not self.prefix:
            raise InvalidPath()
        self.identity = None
        self.lock = threading.Lock()

    @contextmanager
    def directory(self, path=''):
        parts = self.prefix + components(path)
        fd = None
        try:
            if not os.path.ismount(self.mount):
                raise StorageUnavailable()
            fd = os.open(self.mount, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            info = os.fstat(fd)
            identity = (info.st_dev, info.st_ino)
            with self.lock:
                if self.identity is None:
                    self.identity = identity
                if identity != self.identity:
                    raise StorageUnavailable()
            for part in parts:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
                if os.fstat(fd).st_dev != identity[0]:
                    raise InvalidPath()
            yield fd
        except OSError:
            raise StorageUnavailable() from None
        finally:
            if fd is not None:
                os.close(fd)

    def listing(self, path='', after='', limit=100):
        if not 1 <= limit <= 200 or len(after) > 255 or '/' in after or '\\' in after:
            raise InvalidPath()
        with self.directory(path) as fd:
            def entries():
                with os.scandir(fd) as iterator:
                    for count, entry in enumerate(iterator):
                        if count >= 10000:
                            raise StorageUnavailable()
                        if entry.name <= after:
                            continue
                        try:
                            components(entry.name)
                        except (InvalidPath, UnicodeError):
                            continue
                        info = entry.stat(follow_symlinks=False)
                        if info.st_dev != os.fstat(fd).st_dev:
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            kind = 'directory'
                        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                            kind = 'file'
                        else:
                            continue
                        yield {'name': entry.name, 'kind': kind, 'size': info.st_size if kind == 'file' else None}
            selected = heapq.nsmallest(limit + 1, entries(), key=lambda e: e['name'])
        return {'entries': selected[:limit], 'next': selected[limit - 1]['name'] if len(selected) > limit else None}

    @contextmanager
    def open_file(self, path):
        parts = components(path)
        if not parts:
            raise InvalidPath()
        with self.directory('/'.join(parts[:-1])) as parent:
            fd = None
            try:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_dev != os.fstat(parent).st_dev:
                    raise InvalidPath()
                signature = f'{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}'
                etag = '"' + hashlib.sha256(signature.encode()).hexdigest() + '"'
                yield fd, info.st_size, etag
            except OSError:
                raise StorageUnavailable() from None
            finally:
                if fd is not None:
                    os.close(fd)
