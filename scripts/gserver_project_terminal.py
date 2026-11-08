#!/usr/bin/env python3
"""Resolve a GitHub repository through the existing admitted Gserver Host route."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

WORKSPACE = Path('/home/gace/Project/Gserver/workspace/G-ACE.code-workspace')
PROJECTS = Path('/home/gace/Project/Gserver/projects')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
SKIP_DIRECTORIES = {'.git', '.next', '.venv', '.codex-preserve', 'node_modules',
                    'dist', 'build', 'archive', 'backups', 'logs', '旧project'}
MAX_PROJECT_DEPTH = 8
MAX_PROJECT_DIRECTORIES = 10000


def identity(repository, sha):
    if (not isinstance(repository, str) or not REPOSITORY.fullmatch(repository) or
            any(part in {'.', '..'} for part in repository.split('/')) or
            (sha is not None and (not isinstance(sha, str) or not SHA.fullmatch(sha)))):
        raise ValueError('PROJECT_IDENTITY_INVALID')


def project_checkouts(projects):
    """Find existing checkouts below the registered projects parent."""
    pending = [(projects, 0)]
    visited = 0
    while pending:
        parent, depth = pending.pop()
        visited += 1
        if visited > MAX_PROJECT_DIRECTORIES:
            raise ValueError('PROJECT_DISCOVERY_LIMIT')
        for child in parent.iterdir():
            if child.name in SKIP_DIRECTORIES or child.name.startswith('.'):
                continue
            if child.is_symlink() or not child.is_dir():
                continue
            if (child / '.git').exists():
                yield child
            elif depth < MAX_PROJECT_DEPTH:
                pending.append((child, depth + 1))


def workspace_paths(workspace, projects):
    if workspace.is_symlink() or not workspace.is_file():
        raise ValueError('WORKSPACE_UNAVAILABLE')
    document = json.loads(workspace.read_text(encoding='utf-8'))
    folders = document.get('folders') if isinstance(document, dict) else None
    if not isinstance(folders, list):
        raise ValueError('WORKSPACE_FOLDERS_INVALID')
    paths = []
    for item in folders:
        if isinstance(item, dict) and isinstance(item.get('path'), str):
            paths.append(Path(item['path']))
    # The projects parent is already a Workspace folder. Existing subprojects
    # may contain nested repositories; never clone over a missed checkout.
    if projects.is_symlink() or not projects.is_dir():
        raise ValueError('PROJECTS_ROOT_UNAVAILABLE')
    paths.extend(project_checkouts(projects))
    return paths


def find_checkout(repository, workspace=WORKSPACE, projects=PROJECTS):
    valid = {f'https://github.com/{repository}', f'https://github.com/{repository}.git',
             f'git@github.com:{repository}.git', f'git@github.com:{repository}'}
    matches = []
    for path in workspace_paths(workspace, projects):
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            continue
        try:
            if path.resolve(strict=True) != path or not (path / '.git').exists():
                continue
            origin = subprocess.run(['git', '-C', str(path), 'remote', 'get-url', 'origin'],
                                    capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            if origin in valid and path not in matches:
                matches.append(path)
        except (OSError, subprocess.SubprocessError):
            continue
    if len(matches) > 1:
        raise ValueError('PROJECT_CHECKOUT_NOT_UNIQUE')
    return matches[0] if matches else None


def head(path):
    try:
        return subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, timeout=5,
                              check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise ValueError('PROJECT_HEAD_UNAVAILABLE') from None


def clone_checkout(repository, projects=PROJECTS, *, source_url=None):
    """Create one owner-private direct child; never replace an existing path."""
    if projects.is_symlink() or not projects.is_dir() or projects.resolve(strict=True) != projects:
        raise ValueError('PROJECTS_ROOT_UNAVAILABLE')
    owner, name = repository.split('/')
    destination = projects / (owner + '--' + name)
    if destination.exists() or destination.is_symlink():
        raise ValueError('PROJECT_DESTINATION_CONFLICT')
    stage = Path(tempfile.mkdtemp(prefix='.terminal-clone-', dir=projects))
    try:
        url = source_url or f'git@github.com:{repository}.git'
        result = subprocess.run(['git', 'clone', '--quiet', '--', url, str(stage)],
                                capture_output=True, text=True, timeout=180, check=False,
                                env={**os.environ, 'GIT_SSH_COMMAND':
                                     'ssh -o BatchMode=yes -o ConnectTimeout=15'})
        if result.returncode != 0 or not (stage / '.git').is_dir():
            raise ValueError('PROJECT_CLONE_FAILED')
        if destination.exists() or destination.is_symlink():
            raise ValueError('PROJECT_DESTINATION_CONFLICT')
        stage.rename(destination)
        return destination
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('PROJECT_CLONE_FAILED') from None
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def checkout(repository, sha=None, workspace=WORKSPACE, projects=PROJECTS):
    identity(repository, sha)
    path = find_checkout(repository, workspace, projects)
    if path is None:
        lock = projects / '.gserver-project-terminal.lock'
        with lock.open('a+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            path = find_checkout(repository, workspace, projects)
            if path is None:
                path = clone_checkout(repository, projects)
    actual = head(path)
    if sha is not None and actual != sha:
        raise ValueError('PROJECT_SHA_MISMATCH')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--sha')
    parser.add_argument('--workspace', type=Path, default=WORKSPACE)
    parser.add_argument('--projects-root', type=Path, default=PROJECTS)
    parser.add_argument('command')
    args = parser.parse_args(argv)
    try:
        path = checkout(args.repository, args.sha, args.workspace, args.projects_root)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('PROJECT_TERMINAL_DENIED=' + str(exc), file=sys.stderr)
        return 2
    print('PROJECT_TERMINAL_REPOSITORY=' + args.repository)
    print('PROJECT_TERMINAL_HEAD=' + head(path))
    try:
        return subprocess.run(['/bin/bash', '-lc', args.command], cwd=path,
                              env=os.environ.copy(), timeout=3600, check=False).returncode
    except subprocess.TimeoutExpired:
        print('PROJECT_TERMINAL_COMMAND_TIMEOUT', file=sys.stderr)
        return 124


if __name__ == '__main__':
    sys.exit(main())
