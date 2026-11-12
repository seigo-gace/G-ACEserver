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
             f'git@github.com:{repository}.git', f'git@github.com:{repository}',
             origin_url(repository)}
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


def origin_url(repository):
    return f"git@github.com:{repository}.git"


def github_project_registered(repository):
    """True when GitHub Project #1 already has an Issue or PR for this repository."""
    try:
        result = subprocess.run(
            ["gh", "api", "-X", "GET", "search/issues",
             "-f", "q=repo:" + repository + " project:seigo-gace/1"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("PROJECT_REGISTRATION_UNVERIFIED") from None
    if result.returncode:
        if "Validation Failed" in result.stderr or "HTTP 422" in result.stderr:
            return False
        raise ValueError("PROJECT_REGISTRATION_UNVERIFIED")
    try:
        total = json.loads(result.stdout).get("total_count")
    except (ValueError, AttributeError):
        raise ValueError("PROJECT_REGISTRATION_UNVERIFIED") from None
    if type(total) is not int or total < 0:
        raise ValueError("PROJECT_REGISTRATION_UNVERIFIED")
    return total > 0


def clone_checkout(repository, projects):
    """Place one missing registered repository directly under the projects root."""
    destination = projects / repository.replace("/", "--")
    root = projects.resolve(strict=True)
    if destination.parent.resolve(strict=True) != root or destination.is_symlink() or destination.exists():
        raise ValueError("PROJECT_PLACEMENT_OCCUPIED")
    lock_path = projects / ".gserver-project-terminal.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if destination.is_symlink() or destination.exists():
            raise ValueError("PROJECT_PLACEMENT_OCCUPIED")
        completed = subprocess.run(
            ["git", "clone", "--origin", "origin", "--", origin_url(repository), str(destination)],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if completed.returncode or destination.is_symlink() or not (destination / ".git").exists():
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            raise ValueError("PROJECT_CHECKOUT_UNAVAILABLE")
        return destination
    finally:
        os.close(fd)


def head(path):
    try:
        return subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, timeout=5,
                              check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise ValueError('PROJECT_HEAD_UNAVAILABLE') from None


def checkout(repository, sha=None, workspace=WORKSPACE, projects=PROJECTS, admit=None):
    """Reuse one existing checkout. Clone a Project #1 repository only once.

    Ordinary reads omit ``sha`` and run at the checkout's current HEAD. ``sha``
    is the source-update pin and is checked after the checkout is selected.
    An unregistered repository is never cloned. A missing registered
    repository is placed once at ``projects/<owner>--<name>``.
    """
    identity(repository, sha)
    if projects.is_symlink() or not projects.is_dir():
        raise ValueError('PROJECTS_ROOT_UNAVAILABLE')
    if not (github_project_registered if admit is None else admit)(repository):
        raise ValueError('PROJECT_NOT_REGISTERED')
    path = find_checkout(repository, workspace, projects)
    if path is None:
        clone_checkout(repository, projects)
        path = find_checkout(repository, workspace, projects)
    if path is None:
        raise ValueError('PROJECT_CHECKOUT_UNAVAILABLE')
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
        exit_code = subprocess.run(['/bin/bash', '-lc', args.command], cwd=path,
                                   env=os.environ.copy(), timeout=3600, check=False).returncode
        if exit_code != 0:
            print('PROJECT_TERMINAL_COMMAND_EXIT_CODE=' + str(exit_code), file=sys.stderr)
        return exit_code
    except subprocess.TimeoutExpired:
        print('PROJECT_TERMINAL_COMMAND_TIMEOUT', file=sys.stderr)
        return 124


if __name__ == '__main__':
    sys.exit(main())
