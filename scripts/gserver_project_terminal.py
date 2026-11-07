#!/usr/bin/env python3
"""Run a command in a checkout registered in the existing Gserver Workspace."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

WORKSPACE = Path('/home/gace/Project/Gserver/workspace/G-ACE.code-workspace')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')


def checkout(repository, sha, workspace=WORKSPACE):
    if (not REPOSITORY.fullmatch(repository) or
            any(part in {'.', '..'} for part in repository.split('/')) or
            not SHA.fullmatch(sha)):
        raise ValueError('PROJECT_IDENTITY_INVALID')
    if workspace.is_symlink() or not workspace.is_file():
        raise ValueError('WORKSPACE_UNAVAILABLE')
    document = json.loads(workspace.read_text(encoding='utf-8'))
    folders = document.get('folders') if isinstance(document, dict) else None
    if not isinstance(folders, list):
        raise ValueError('WORKSPACE_FOLDERS_INVALID')
    matches = []
    for item in folders:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            continue
        path = Path(item['path'])
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            continue
        try:
            resolved = path.resolve(strict=True)
            if resolved != path or not (path / '.git').exists():
                continue
            origin = subprocess.run(['git', '-C', str(path), 'remote', 'get-url', 'origin'],
                                    capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            valid = {f'https://github.com/{repository}', f'https://github.com/{repository}.git',
                     f'git@github.com:{repository}.git'}
            if origin not in valid:
                continue
            head = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            if head == sha:
                matches.append(path)
        except (OSError, subprocess.SubprocessError):
            continue
    if len(matches) != 1:
        raise ValueError('PROJECT_CHECKOUT_NOT_UNIQUE_OR_SHA_MISMATCH')
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--workspace', type=Path, default=WORKSPACE)
    parser.add_argument('command')
    args = parser.parse_args(argv)
    try:
        path = checkout(args.repository, args.sha, args.workspace)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('PROJECT_TERMINAL_DENIED=' + str(exc), file=sys.stderr)
        return 2
    try:
        return subprocess.run(['/bin/bash', '-lc', args.command], cwd=path,
                              env=os.environ.copy(), timeout=3600, check=False).returncode
    except subprocess.TimeoutExpired:
        print('PROJECT_TERMINAL_COMMAND_TIMEOUT', file=sys.stderr)
        return 124


if __name__ == '__main__':
    sys.exit(main())
