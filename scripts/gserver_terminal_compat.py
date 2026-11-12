#!/usr/bin/env python3
"""Build one current host.command request. Default off. No new route.

The resident terminal host does not import this module. Turning the flag on
still supplies the existing mandatory dispatcher SHA and measured G-ACEserver
HEAD. It does not drop them, sign a delivery, or contact Gateway.
"""
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess

FLAG = "GSERVER_TERMINAL_DIRECT_EXECUTE"
REPOSITORY = "seigo-gace/G-ACEserver"
TARGET = "gserver"
SCHEMA = "gace.servercore-bounded-host.request/v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
REQUEST_ID = re.compile(r"^req_[0-9a-f]{24}$")
PROJECT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class CompatError(ValueError):
    pass


def enabled(env=None):
    return (os.environ if env is None else env).get(FLAG) == "1"


def _head(root):
    path = Path(root)
    if path.is_symlink() or not path.is_dir() or not (path / ".git").exists():
        raise CompatError("GSERVER_TERMINAL_ROOT_INVALID")
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise CompatError("GSERVER_TERMINAL_GIT_UNAVAILABLE") from None
    value = result.stdout.strip()
    if result.returncode or not SHA.fullmatch(value):
        raise CompatError("GSERVER_TERMINAL_GIT_HEAD_INVALID")
    return value


def build_request(*, request_id, project_repository, command, expected_sha, root,
                  operation_class="read", explicit_sha=None, env=None):
    """Return the current adapter request, or refuse while the flag is off."""
    if not enabled(env):
        raise CompatError("GSERVER_TERMINAL_COMPAT_DISABLED")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise CompatError("GSERVER_TERMINAL_REQUEST_ID_INVALID")
    if (not isinstance(project_repository, str) or not PROJECT.fullmatch(project_repository)
            or any(part in {".", ".."} for part in project_repository.split("/"))):
        raise CompatError("GSERVER_TERMINAL_PROJECT_INVALID")
    if not isinstance(command, str) or not command or "\x00" in command:
        raise CompatError("GSERVER_TERMINAL_COMMAND_INVALID")
    if operation_class not in {"read", "write"}:
        raise CompatError("GSERVER_TERMINAL_OPERATION_INVALID")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise CompatError("GSERVER_TERMINAL_DISPATCHER_SHA_REQUIRED")
    if explicit_sha is not None and (not isinstance(explicit_sha, str) or not SHA.fullmatch(explicit_sha)):
        raise CompatError("GSERVER_TERMINAL_PIN_INVALID")
    if operation_class == "write" and explicit_sha is None:
        raise CompatError("GSERVER_TERMINAL_WRITE_PIN_REQUIRED")
    host_sha = _head(root)
    if project_repository == REPOSITORY:
        if explicit_sha is not None and explicit_sha != host_sha:
            raise CompatError("GSERVER_TERMINAL_HOST_SHA_MISMATCH")
        if operation_class == "write" and explicit_sha != host_sha:
            raise CompatError("GSERVER_TERMINAL_HOST_SHA_MISMATCH")
        wire = command
    else:
        helper = Path(__file__).resolve().with_name("gserver_project_terminal.py")
        argv = [str(helper), "--repository", project_repository]
        if explicit_sha is not None:
            argv.extend(["--sha", explicit_sha])
        wire = "python3 -B " + " ".join(shlex.quote(part) for part in argv + [command])
    return {
        "schema": SCHEMA, "id": request_id, "command_id": "host.command",
        "expected_sha": expected_sha, "repository": REPOSITORY, "repo_sha": host_sha,
        "command": wire, "command_sha256": hashlib.sha256(wire.encode("utf-8")).hexdigest(),
        "host_target": TARGET,
    }
