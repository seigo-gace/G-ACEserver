#!/usr/bin/env python3
"""Bounded real G: acceptance test, only on a newly-created temporary folder."""
import hashlib
import os
from pathlib import Path
import tempfile

from gserver_files import DRIVE, FILES, put, get
from storage import Storage, StorageUnavailable
from storage_mutations import digest, quota, replace_version, to_trash, restore, trash_list


def run(mount=DRIVE, files=FILES):
    mount = Path(mount)
    files = Path(files)
    if not os.path.ismount(mount):
        raise StorageUnavailable('G: mount absent')
    if not files.is_dir() or files.is_symlink() or files.parent.is_symlink():
        raise StorageUnavailable('dedicated Gserver files root not safe')
    # TemporaryDirectory is exclusively created by this test; no preexisting
    # user path is opened for writing, replaced, deleted or given new ACLs.
    with tempfile.TemporaryDirectory(prefix='gserver-accept-', dir=files) as isolated:
        with tempfile.TemporaryDirectory(prefix='gserver-src-') as incoming:
            scoped = Storage(str(mount), str(Path(isolated)))
            source = Path(incoming) / 'sample.bin'
            source.write_bytes(os.urandom(1024 * 1024 + 17))
            original = put(str(source), mount, Path(isolated), reserve_bytes=0)
            assert digest(scoped, 'sample.bin')['sha256'] == original['sha256']
            replacement = Path(incoming) / 'updated.bin'
            replacement.write_bytes(os.urandom(512 * 1024 + 19))
            with open(replacement, 'rb') as stream:
                changed = replace_version(scoped, 'sample.bin', stream.fileno(), original['sha256'], reserve_bytes=0)
            assert changed['old_sha256'] == original['sha256']
            assert digest(scoped, 'sample.bin')['sha256'] == changed['sha256']
            assert len(trash_list(scoped)['entries']) == 1
            deleted = to_trash(scoped, 'sample.bin', changed['sha256'])
            assert scoped.listing()['entries'] == []
            restored = restore(scoped, deleted['restore_id'], 'sample.bin', changed['sha256'])
            assert restored['sha256'] == changed['sha256']
            with tempfile.TemporaryDirectory(prefix='gserver-dl-') as downloads:
                saved = get('sample.bin', downloads, mount, Path(isolated))
                assert saved['sha256'] == changed['sha256']
                assert hashlib.sha256((Path(downloads) / 'sample.bin').read_bytes()).hexdigest() == changed['sha256']
            assert quota(scoped)['available_bytes'] >= 0
            return {'checks': ['put', 'hash', 'replace', 'trash', 'restore', 'get', 'quota'],
                    'bytes_verified': original['bytes'] + changed['bytes'],
                    'isolated_test_folder_only': True}


def main():
    print('========== GACE_RESULT_BEGIN ==========')
    print('PROJECT=Gserver')
    print('ACTION=G_STORAGE_MUTATIONS_HOST_ISOLATED')
    try:
        result = run()
        print('CHECKS=' + ','.join(result['checks']))
        print('BYTES_VERIFIED=' + str(result['bytes_verified']))
        print('USER_FILES_MODIFIED=NONE')
        print('SMB_FIREWALL_CHANGED=False')
        print('VERIFY=PASS')
    except (AssertionError, OSError, StorageUnavailable, ValueError) as exc:
        print('ERROR_TYPE=' + type(exc).__name__)
        print('USER_FILES_MODIFIED=NONE')
        print('VERIFY=FAIL')
        raise SystemExit(1)
    finally:
        print('PROJECT_END=Gserver')
        print('========== GACE_RESULT_END ==========')


if __name__ == '__main__':
    main()
