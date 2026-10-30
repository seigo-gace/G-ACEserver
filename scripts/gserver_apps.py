#!/usr/bin/env python3
"""Operate an existing, independently packaged Gserver application via local Docker Compose.

The Gserver core project, its volumes, and other apps are never selected.  This
operator does not build/pull images, create external ingress, or remove volumes.
Apps own their Compose files and any required credentials; this is not an app
runtime and contains no Telegram/Tumblr-specific code.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

NAME = re.compile(r"[a-z][a-z0-9-]{0,39}\Z")
DOCKER_SOCKET = "unix:///var/run/docker.sock"


class AppError(Exception):
    pass


def compose_file(path):
    file = Path(path).expanduser().absolute()
    try:
        info = file.lstat()
    except OSError as exc:
        raise AppError("COMPOSE_FILE_UNAVAILABLE") from exc
    if not stat.S_ISREG(info.st_mode) or file.is_symlink() or info.st_size > 2_000_000:
        raise AppError("COMPOSE_FILE_UNSAFE")
    return file


def project(name):
    if not NAME.fullmatch(name):
        raise AppError("INVALID_APP_NAME")
    return "gace-app-" + name


def command(file, name):
    # Force the local daemon; never target a remote Docker context.
    docker = ["docker"] if os.geteuid() == 0 else ["sudo", "-n", "docker"]
    return docker + ["--host", DOCKER_SOCKET, "compose", "--project-name", project(name),
                     "--project-directory", str(file.parent), "--env-file", "/dev/null", "-f", str(file)]


def run(argv, timeout=90):
    try:
        result = subprocess.run(argv, check=False, text=True,
                                capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AppError("DOCKER_COMMAND_FAILED") from exc
    if result.returncode != 0:
        # Don't print Docker stderr; Compose may reveal environment variables.
        raise AppError("DOCKER_COMMAND_FAILED")
    return result.stdout


def validate(file, name):
    root = command(file, name)
    raw = run(root + ["config", "--format", "json"])
    try:
        config = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise AppError("COMPOSE_CONFIG_INVALID") from exc
    services = config.get("services") if isinstance(config, dict) else None
    if not isinstance(services, dict) or not services:
        raise AppError("COMPOSE_SERVICES_MISSING")
    for key in ("networks", "volumes"):
        definitions = config.get(key, {}) or {}
        if not isinstance(definitions, dict) or any(
            not isinstance(value, dict) or value.get("external")
            for value in definitions.values()
        ):
            raise AppError("EXTERNAL_RESOURCE_NOT_ALLOWED")
    for svc in services.values():
        if not isinstance(svc, dict):
            raise AppError("COMPOSE_SERVICE_INVALID")
        if svc.get("build"):
            raise AppError("BUILD_NOT_ALLOWED")
        if svc.get("container_name") or svc.get("volumes_from") or svc.get("userns_mode") == "host":
            raise AppError("CROSS_PROJECT_CONTAINER_NOT_ALLOWED")
        if svc.get("privileged") or svc.get("pid") == "host" or svc.get("ipc") == "host":
            raise AppError("HOST_PRIVILEGES_NOT_ALLOWED")
        if svc.get("network_mode") not in (None, "none") or svc.get("devices") or svc.get("cap_add"):
            raise AppError("HOST_PRIVILEGES_NOT_ALLOWED")
        for port in svc.get("ports", []) or []:
            # Block unexpected LAN/public exposure; apps remain local until
            # an independently approved authenticated ingress is configured.
            if not isinstance(port, dict) or port.get("host_ip") not in ("127.0.0.1", "::1"):
                raise AppError("PUBLIC_PORT_NOT_ALLOWED")
        for volume in svc.get("volumes", []) or []:
            if isinstance(volume, dict) and volume.get("type") == "bind":
                target = str(volume.get("source", ""))
                if target == "/var/run/docker.sock" or target == "/" or target.startswith("/run/docker"):
                    raise AppError("HOST_SOCKET_OR_ROOT_MOUNT_NOT_ALLOWED")
    return root, sorted(services)


def execute(action, file, name):
    root, services = validate(compose_file(file), name)
    print("PROJECT=" + project(name))
    print("SERVICES=" + ",".join(services))
    if action == "verify":
        print("APP_CONFIG=PASS")
    elif action == "start":
        run(root + ["up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "60"], timeout=180)
        print("APP_START=PASS")
    elif action == "stop":
        run(root + ["stop", "--timeout", "10"])
        print("APP_STOP=PASS")
    elif action == "status":
        stdout = run(root + ["ps", "--all", "--format", "json"])
        try:
            records = json.loads(stdout) if stdout.strip().startswith("[") else [json.loads(s) for s in stdout.splitlines() if s.strip()]
        except (ValueError, TypeError) as exc:
            raise AppError("STATUS_FORMAT_INVALID") from exc
        for row in records:
            if not isinstance(row, dict):
                raise AppError("STATUS_FORMAT_INVALID")
            svc = str(row.get("Service", ""))
            state = str(row.get("State", ""))
            if svc not in services or state not in ("running", "exited", "created", "restarting", "paused", "dead"):
                raise AppError("STATUS_FORMAT_INVALID")
            print("APP_SERVICE=" + svc + ";STATE=" + state)
        print("APP_STATUS=PASS")
    elif action == "logs":
        # bounded lines, then bounded bytes, no dumping full app logs to caller
        stdout = run(root + ["logs", "--tail", "20", "--no-color"])
        print("APP_LOG_BYTES=" + str(len(stdout.encode())))
        print("APP_LOGS_AVAILABLE=PASS")
    else:
        raise AppError("INVALID_ACTION")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "start", "stop", "status", "logs"))
    parser.add_argument("name", help="App label: lowercase letters, digits, and dashes")
    parser.add_argument("compose", help="Existing Compose YAML path (app-owned)")
    args = parser.parse_args()
    try:
        execute(args.action, args.compose, args.name)
    except AppError as exc:
        print("GSERVER_APP_ERROR=" + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
