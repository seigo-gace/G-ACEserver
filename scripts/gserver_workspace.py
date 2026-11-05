#!/usr/bin/env python3
"""Wire the existing server-core into the local workspace, without provider changes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


class WorkspaceError(Exception):
    pass


def git(core, *args):
    try:
        return subprocess.run(['git', '-C', str(core), *args], check=True,
                              capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise WorkspaceError('SERVERCORE_GIT_UNVERIFIED') from None


def canonical(path):
    if not path.is_absolute() or path != path.resolve():
        raise WorkspaceError('WORKSPACE_PATH_ALIAS_REJECTED')
    return path


def source(core):
    canonical(core)
    if not core.is_dir() or git(core, 'rev-parse', '--show-toplevel') != str(core):
        raise WorkspaceError('SERVERCORE_CHECKOUT_UNVERIFIED')
    origin = git(core, 'remote', 'get-url', 'origin')
    if origin not in ('git@github.com:G-ACE-inc/server-core.git',
                      'https://github.com/G-ACE-inc/server-core.git',
                      'https://github.com/G-ACE-inc/server-core'):
        raise WorkspaceError('SERVERCORE_ORIGIN_MISMATCH')
    if git(core, 'status', '--porcelain', '--untracked-files=no'):
        raise WorkspaceError('SERVERCORE_TRACKED_SOURCE_DIRTY')
    sha = git(core, 'rev-parse', 'HEAD')
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise WorkspaceError('SERVERCORE_SHA_INVALID')
    for name in ('README.md', 'docs/LOAD_SCOPE.md', 'operations/github-project-rule-plane.json',
                 'operations/github-project-bounded-host.json', 'scripts/workspace_command_center_check.py'):
        path = core / name
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            raise WorkspaceError('SERVERCORE_AUTHORITY_MISSING')
        git(core, 'ls-files', '--error-unmatch', name)
    manifest = json.loads((core / 'operations/github-project-rule-plane.json').read_text())
    rule = manifest['rule_planes']['server_ai']
    if rule['issue_number'] != 16 or manifest['rule_planes']['gpt_chat']['server_ai_default_load'] is not False:
        raise WorkspaceError('RULE_PLANE_PROFILE_MISMATCH')
    return sha


def layout(core, projects):
    # Reuse the owning helper; do not fork its folder/exclusion policy.
    name = '_gserver_workspace_upstream'
    spec = importlib.util.spec_from_file_location(name, core / 'scripts/workspace_command_center_check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.expected_workspace(core, projects)


def artifacts(core, projects, workspace):
    canonical(projects)
    canonical(workspace)
    if not projects.is_dir() or core == projects or projects in core.parents or core in projects.parents:
        raise WorkspaceError('WORKSPACE_ROOTS_MUST_BE_DISTINCT')
    # Caller-owned paths only; do not write rules into an arbitrary shared root.
    for directory in (core, projects):
        if directory.stat().st_uid != os.getuid():
            raise WorkspaceError('WORKSPACE_DIRECTORY_OWNER_MISMATCH')
    entry = f'''# G-ACE Workspace — local entry

server-core is the command center: `{core}/README.md` → `docs/LOAD_SCOPE.md`
→ `operations/github-project-rule-plane.json` → SERVER_AI Rule #16 → target Current.
Use the canonical GitHub Project #1 and owning repository; do not copy full rules.
SERVER_AI uses normal local tools. GPT CHAT #17 / Agent Loop remains its own profile.
Existing model/cost settings and user-selected lead remain unchanged.

Local source-loading path is `{core}`; `/home/admin1/server-core` in upstream
VPS contracts remains the remote Contabo execution root, never a local admission.
The local projects root is `{projects}`. Keep each project's code and data there.
Local Core/apps continue operating when GitHub or Contabo is unavailable.
Remote work must select the verified Host target, actual Source SHAs and original
request/Run/result; a workspace file grants no remote shell or deploy authority.
'''
    rule = f'''---
description: G-ACE Workspace local path adapter; canonical server-core rules remain authoritative.
alwaysApply: true
---

Read `{core}/README.md`, then its LOAD_SCOPE and rule-plane manifest.
Apply SERVER_AI #16 and the target repository Current; do not default-load #17.
Use `{core}` for local authority loading. Upstream `/home/admin1/server-core`
paths belong to the Contabo runtime; never execute them locally or rewrite its
Host registry to grant Gserver access. Use registered Host targets and evidence.
Keep user-selected model/cost settings. Do not create another AI or scheduler.
'''
    local_source_rule = '''---
description: Local Gserver checkout path mapping; upstream runtime contracts are unchanged.
alwaysApply: true
---

This is the local Gserver copy of the same authoritative server-core repository.
For authority loading use this folder's README.md, docs/LOAD_SCOPE.md and manifest.
Literal /home/admin1/server-core references in the upstream bootstrap describe the
VPS checkout. They are not local paths: resolve authority files in this server-core
folder, while preserving remote Host target/root/SHA admission for actual commands.
Apply SERVER_AI #16; do not load GPT CHAT #17/Notion/Agent Loop as executor rules.
A local checkout and workspace never grant Contabo/Gserver remote deploy authority.
'''
    return {
        core / '.cursor/rules/00_gserver_local_paths.mdc': local_source_rule,
        workspace: json.dumps(layout(core, projects), ensure_ascii=False, indent=2) + '\n',
        projects / 'AGENTS.md': entry,
        projects / '.cursor/rules/00_gace_workspace.mdc': rule,
    }


def install(files):
    # Preflight every file before the first write. Preserve all existing content.
    for path, content in files.items():
        canonical(path)
        if path.exists() and (not path.is_file() or path.read_text() != content):
            raise WorkspaceError('EXISTING_WORKSPACE_FILE_CONFLICT')
    created = []
    try:
        for path, content in files.items():
            if path.exists():
                continue
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            canonical(path.parent)
            if path.parent.stat().st_uid != os.getuid():
                raise WorkspaceError('WORKSPACE_DIRECTORY_OWNER_MISMATCH')
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            info = os.fstat(fd)
            created.append((path, info.st_dev, info.st_ino))
            with os.fdopen(fd, 'w') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path, device, inode in reversed(created):
            # Only our newly created files; never delete a concurrent replacement.
            try:
                info = path.lstat()
                if not path.is_symlink() and (info.st_dev, info.st_ino) == (device, inode):
                    path.unlink()
            except OSError:
                pass
        raise


def verify(files):
    return all(path.is_file() and not path.is_symlink() and path.read_text() == content
               for path, content in files.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-core', type=Path, default=Path.home() / 'server-core')
    parser.add_argument('--projects', type=Path, default=Path.home() / 'Project')
    parser.add_argument('--workspace', type=Path, default=Path.home() / 'workspace/G-ACE.code-workspace')
    parser.add_argument('--install', action='store_true', help='Create missing files only; refuse existing conflicts')
    args = parser.parse_args(argv)
    try:
        sha = source(args.server_core)
        files = artifacts(args.server_core, args.projects, args.workspace)
        if args.install:
            install(files)
        if not verify(files):
            raise WorkspaceError('WORKSPACE_NOT_INSTALLED_OR_CHANGED')
        print('WORKSPACE_LAYOUT=PASS\nSERVERCORE_SOURCE_SHA=' + sha)
        print('RULE_ROUTING=FILES_VERIFIED\nCLIENT_RULE_LOADING=NOT_VERIFIED')
        print('CONTABO_TERMINAL=NOT_VERIFIED_THIS_CHECK\nGSERVER_REMOTE_TERMINAL=NOT_VERIFIED')
        print('AGENT_LOOP=CANONICAL_REFERENCES_ONLY')
        return 0
    except WorkspaceError as exc:
        print('WORKSPACE_LAYOUT=FAIL\nERROR=' + str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # No native stderr, private inventories or credentials in output.
        print('WORKSPACE_LAYOUT=FAIL\nERROR=WORKSPACE_OPERATION_FAILED', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
