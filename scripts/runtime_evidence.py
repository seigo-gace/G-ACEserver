#!/usr/bin/env python3
"""Store a small local verification receipt, never raw logs or credentials."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile


def save(directory, source, final_source, phase, code):
    for sha in (source, final_source):
        if sha != 'UNKNOWN' and not re.fullmatch(r'[a-f0-9]{40}', sha):
            raise ValueError('invalid source SHA')
    if not re.fullmatch(r'[A-Z_]{1,64}', phase) or not 0 <= code <= 255:
        raise ValueError('invalid result')
    data = {'schema': 'gserver.runtime-verification.v1',
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'source_sha': source, 'final_source_sha': final_source,
            'phase': phase, 'exit_code': code,
            'status': 'PASS' if code == 0 and source == final_source and source != 'UNKNOWN' else 'FAIL',
            'scope': 'isolated_runtime_only', 'f01_f08': 'NOT_COMPLETE'}
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(directory / 'latest.json')
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('final_source')
    parser.add_argument('phase')
    parser.add_argument('code', type=int)
    args = parser.parse_args()
    directory = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'gserver/verification'
    save(directory, args.source, args.final_source, args.phase, args.code)
    print('LOCAL_VERIFICATION_RECEIPT=SAVED')
