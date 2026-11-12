#!/usr/bin/env python3
"""Minimal target-owned writer for the shared server-core host.command contract.

This is an adapter primitive, not a second Terminal: it has no listener,
dispatcher, fixed command menu, Docker authority, credential store or daemon.
An authenticated owner-side Receiver may call ``execute_request`` after it has
verified the Gateway signature and target. Production activation is a separate
Host/Gateway admission gate.
"""
import hashlib
import os
import pwd
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"^[0-9a-f]{40}$")
COMMAND_DIGEST = re.compile(r"^[0-9a-f]{64}$")
REQUEST_ID = re.compile(r"^req_[0-9a-f]{24}$")
REPOSITORY = "seigo-gace/G-ACEserver"
TARGET = "gserver"
MAX_OUTPUT = 262144
DEFAULT_TIMEOUT_SECONDS = 3600
MAX_TIMEOUT_SECONDS = 21600


class HostAdapterError(ValueError):
    pass


def command_timeout(env=None):
    value = (env or os.environ).get("GSERVER_TERMINAL_COMMAND_TIMEOUT_SECONDS",
                                    str(DEFAULT_TIMEOUT_SECONDS))
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        raise HostAdapterError("GSERVER_TIMEOUT_INVALID") from None
    if not 1 <= seconds <= MAX_TIMEOUT_SECONDS:
        raise HostAdapterError("GSERVER_TIMEOUT_INVALID")
    return seconds


def command_environment():
    """Use the login user's normal development environment and credentials."""
    env = dict(os.environ)
    try:
        home = pwd.getpwuid(os.getuid()).pw_dir
    except (KeyError, OSError):
        home = env.get("HOME", "/home/gace")
    env.update({
        "HOME": home,
        "PATH": env.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    return env


def _sha(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir() or not (path / ".git").is_dir():
        raise HostAdapterError("GSERVER_ROOT_INVALID")
    try:
        result = subprocess.run(
            ["git", "-c", "safe.directory=" + str(path), "rev-parse", "HEAD"],
            cwd=path, capture_output=True, text=True, timeout=5, check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_CONFIG_NOSYSTEM": "1"},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HostAdapterError("GSERVER_GIT_UNAVAILABLE") from None
    value = result.stdout.strip()
    if result.returncode or not SHA.fullmatch(value):
        raise HostAdapterError("GSERVER_GIT_HEAD_INVALID")
    return value


def validate_request(request, root):
    required = {"schema", "id", "command_id", "expected_sha", "repository", "repo_sha",
                "command", "command_sha256", "host_target"}
    if not isinstance(request, dict) or set(request) != required:
        raise HostAdapterError("GSERVER_REQUEST_KEYS_INVALID")
    if request["schema"] != "gace.servercore-bounded-host.request/v1":
        raise HostAdapterError("GSERVER_REQUEST_SCHEMA_INVALID")
    if not REQUEST_ID.fullmatch(str(request["id"])):
        raise HostAdapterError("GSERVER_REQUEST_ID_INVALID")
    if request["command_id"] != "host.command" or request["host_target"] != TARGET:
        raise HostAdapterError("GSERVER_TARGET_OR_COMMAND_INVALID")
    if request["repository"] != REPOSITORY or not SHA.fullmatch(str(request["expected_sha"])) \
            or not SHA.fullmatch(str(request["repo_sha"])):
        raise HostAdapterError("GSERVER_REQUEST_TARGET_INVALID")
    command = request["command"]
    if not isinstance(command, str) or not command or "\x00" in command:
        raise HostAdapterError("GSERVER_COMMAND_INVALID")
    digest = request["command_sha256"]
    if not COMMAND_DIGEST.fullmatch(str(digest)) \
            or hashlib.sha256(command.encode("utf-8")).hexdigest() != digest:
        raise HostAdapterError("GSERVER_COMMAND_TRANSPORT_CHANGED")
    host_sha = _sha(root)
    if host_sha != request["repo_sha"]:
        raise HostAdapterError("GSERVER_REPO_SHA_MISMATCH")
    return host_sha


def execute_request(request, root):
    """Run one already-admitted common command and return bounded evidence."""
    root = Path(root).resolve(strict=True)
    host_sha = validate_request(request, root)
    try:
        completed = subprocess.run(
            ["/bin/bash", "-lc", request["command"]], cwd=root,
            capture_output=True, text=False, timeout=command_timeout(), check=False,
            env=command_environment(), close_fds=True,
        )
        stdout = completed.stdout[:MAX_OUTPUT]
        stderr = completed.stderr[:MAX_OUTPUT]
        state = "PASS" if completed.returncode == 0 else "FAIL"
        code = completed.returncode if 0 <= completed.returncode <= 255 else 1
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"")[:MAX_OUTPUT] if isinstance(exc.stdout, bytes) else b""
        stderr = b"GSERVER_COMMAND_TIMEOUT"
        state, code = "FAIL", 124
    # Hash the exact UTF-8 text returned on the wire, including replacement of
    # non-UTF-8 command output. Consumers can independently verify these bytes.
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    result = {
        "request_id": request["id"], "host_target": TARGET, "repository": REPOSITORY,
        "repo_sha": request["repo_sha"], "host_sha": host_sha, "state": state,
        "dispatcher_sha": request["expected_sha"],
        "command_sha256": request["command_sha256"],
        "exit_code": code, "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
        "stdout": stdout_text, "stderr": stderr_text,
    }
    return result
