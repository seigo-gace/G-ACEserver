#!/usr/bin/env python3
"""Foreground acceptance of two disposable Compose apps; never redeploy Core."""
import contextlib
import io
import json
from pathlib import Path
import secrets
import sys
import tempfile

import gserver_apps as apps

DOCKER = (["docker"] if apps.os.geteuid() == 0 else ["sudo", "-n", "docker"]) + ["--host", apps.DOCKER_SOCKET]
CORE = "gace-gserver-gserver-1"


def docker(*args):
    return apps.run(DOCKER + list(args), timeout=180)


def inventory():
    ids = docker("ps", "-aq").split()
    rows = json.loads(docker("inspect", *ids)) if ids else []
    return {row["Id"]: {"image": row["Image"], "started": row["State"]["StartedAt"],
                       "status": row["State"]["Status"], "mounts": row["Mounts"]}
            for row in rows}


def storage():
    # Credentials stay inside the existing container, never argv/stdout/receipt.
    code = """import os, pathlib, urllib.request, hashlib, json
key=pathlib.Path(os.environ['GSERVER_AUTH_FILE']).read_text().strip()
digests=[]
for route in ('ready','files'):
 req=urllib.request.Request('http://127.0.0.1:8765/'+route,headers={'Authorization':'Bearer '+key})
 with urllib.request.urlopen(req,timeout=5) as r:
  assert r.status==200
  digests.append(hashlib.sha256(r.read()).hexdigest())
print(json.dumps(digests))
"""
    result = json.loads(docker("exec", CORE, "python3", "-c", code))
    if not isinstance(result, list) or len(result) != 2 or not all(
            isinstance(value, str) and apps.re.fullmatch(r"[a-f0-9]{64}", value) for value in result):
        raise apps.AppError("STORAGE_CHECK_FAILED")
    return result


def main():
    phase = "PRECHECK"
    created = []
    before = None
    storage_before = None
    failure = None
    print("========== GACE_RESULT_BEGIN ==========", flush=True)
    print("PROJECT=Gserver\nACTION=PC_GENERIC_APP_RUNTIME_SMOKE", flush=True)
    with tempfile.TemporaryDirectory(prefix="gserver-app-smoke-") as directory:
        file = Path(directory) / "compose.json"
        try:
            if apps.os.geteuid() != 0:
                phase = "DOCKER_SUDO_AUTH_REQUIRED"
                apps.run(["sudo", "-n", "true"])
            phase = "PRECHECK"
            before = inventory()
            core = json.loads(docker("inspect", CORE))[0]
            if core["State"].get("Health", {}).get("Status") != "healthy":
                raise apps.AppError("CORE_NOT_HEALTHY")
            image = core["Image"]
            if not apps.re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                raise apps.AppError("CORE_IMAGE_INVALID")
            storage_before = storage()
            names = ["probe-" + secrets.token_hex(8) for _ in range(2)]
            token = secrets.token_hex(16)  # synthetic persistence marker, no real data
            config = {"services": {"probe": {
                "image": image, "network_mode": "none", "restart": "no",
                "user": "65534:65534", "read_only": True,
                "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
                "mem_limit": "64m", "cpus": "0.25", "pids_limit": 32,
                "logging": {"driver": "local", "options": {"max-size": "1m", "max-file": "1"}},
                "volumes": [{"type": "volume", "source": "state", "target": "/var/lib/gserver"}],
                "command": ["python3", "-u", "-c",
                    "from pathlib import Path; import time; p=Path('/var/lib/gserver/app-probe'); "
                    + f"p.write_text('{token}') if not p.exists() else None; "
                    + "print('app probe ready',flush=True); time.sleep(600)"],
                "healthcheck": {"test": ["CMD", "python3", "-c",
                    "from pathlib import Path; assert Path('/var/lib/gserver/app-probe').is_file()"],
                    "interval": "1s", "timeout": "2s", "retries": 10},
                "labels": {"gserver.probe.revision": "1"}}}, "volumes": {"state": {}}}

            def write():
                file.write_text(json.dumps(config))

            def operate(action, name):
                with contextlib.redirect_stdout(io.StringIO()):
                    apps.execute(action, file, name)

            def container(name):
                root = apps.command(file, name)
                ids = apps.run(root + ["ps", "-q", "probe"]).split()
                if len(ids) != 1:
                    raise apps.AppError("PROBE_NOT_RUNNING")
                return ids[0]

            def persisted(name):
                value = docker("exec", container(name), "python3", "-c",
                               "from pathlib import Path; print(Path('/var/lib/gserver/app-probe').read_text())").strip()
                if value != token:
                    raise apps.AppError("APP_PERSISTENCE_FAILED")

            write()
            for name in names:
                phase = "PROJECT_GUARD"
                for kind, args in (("ps", ["-aq"]), ("network", ["ls", "-q"]), ("volume", ["ls", "-q"])):
                    if docker(kind, *args, "--filter", "label=com.docker.compose.project=" + apps.project(name)).strip():
                        raise apps.AppError("PROBE_PROJECT_EXISTS")
                # Also guard explicit resource names, including unlabeled objects.
                for kind in ("network", "volume"):
                    if any(value.startswith(apps.project(name) + "_") for value in docker(kind, "ls", "--format", "{{.Name}}").splitlines()):
                        raise apps.AppError("PROBE_RESOURCE_EXISTS")
                phase = "APP_START"
                created.append(name)
                operate("start", name)
                persisted(name)
            print("APP_TWO_PROJECTS_RUNNING=PASS", flush=True)
            phase = "STOP_ISOLATION"
            second_id = container(names[1])
            operate("stop", names[0])
            rows = json.loads(apps.run(apps.command(file, names[0]) + ["ps", "--all", "--format", "json"]))
            if isinstance(rows, dict):
                rows = [rows]
            if len(rows) != 1 or rows[0]["State"] != "exited" or container(names[1]) != second_id:
                raise apps.AppError("APP_STOP_ISOLATION_FAILED")
            operate("start", names[0])
            persisted(names[0])
            print("APP_STOP_START_PERSISTENCE=PASS", flush=True)
            phase = "UPDATE_ROLLBACK"
            for revision in ("2", "1"):
                previous_id = container(names[0])
                config["services"]["probe"]["labels"]["gserver.probe.revision"] = revision
                write()
                operate("start", names[0])
                current_id = container(names[0])
                row = json.loads(docker("inspect", current_id))[0]
                if current_id == previous_id or row["Config"]["Labels"]["gserver.probe.revision"] != revision:
                    raise apps.AppError("APP_RECREATE_FAILED")
                persisted(names[0])
            operate("status", names[0])
            operate("logs", names[0])
            print("APP_CONFIG_UPDATE_ROLLBACK=PASS", flush=True)
        except (apps.AppError, OSError, ValueError, KeyError, TypeError) as exc:
            failure = phase
            # No ordinary app logs/configuration are dumped. These are our own
            # random synthetic projects, created only after collision guards.
            code = str(exc) if isinstance(exc, apps.AppError) else type(exc).__name__
            if apps.re.fullmatch(r"[A-Z_]+", code):
                print("APP_FAILURE_DETAIL=" + code, flush=True)
            if phase in ("APP_START", "STOP_ISOLATION", "UPDATE_ROLLBACK"):
                for name in created:
                    try:
                        ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + apps.project(name)).split()
                        for container_id in ids:
                            row = json.loads(docker("inspect", container_id))[0]
                            if row.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") != apps.project(name):
                                continue
                            state = row.get("State", {})
                            print("PROBE_EXIT_CODE=" + str(int(state.get("ExitCode", -1))))
                            print("PROBE_OOM_KILLED=" + str(bool(state.get("OOMKilled", False))))
                            # Only classified error types, never paths/tokens.
                            log = docker("logs", "--tail", "20", container_id)
                            for error in ("PermissionError", "FileNotFoundError", "SyntaxError", "Read-only file system", "ModuleNotFoundError"):
                                if error in log:
                                    print("PROBE_PROCESS_ERROR=" + error.replace(" ", "_"))
                    except (apps.AppError, ValueError, KeyError, TypeError):
                        print("PROBE_DIAGNOSTIC=UNAVAILABLE")
                diagnostic = getattr(exc, "diagnostic", "").lower()
                for fragment, reason in (("permission denied", "PERMISSION_DENIED"),
                        ("no such image", "LOCAL_IMAGE_MISSING"), ("unhealthy", "HEALTHCHECK_FAILED"),
                        ("read-only file system", "READ_ONLY_FILESYSTEM"),
                        ("invalid mount", "MOUNT_REJECTED"), ("exited", "PROCESS_EXITED"),
                        ("cannot allocate memory", "MEMORY_UNAVAILABLE"), ("no space left", "DISK_FULL")):
                    if fragment in diagnostic:
                        print("PROBE_DOCKER_REASON=" + reason)
        finally:
            for name in reversed(created):
                try:
                    # Only the freshly guarded disposable projects, never Core.
                    apps.run(apps.command(file, name) + ["down", "--volumes", "--timeout", "10"])
                except apps.AppError:
                    failure = "CLEANUP"
            if before is not None:
                try:
                    if inventory() != before:
                        raise apps.AppError("CORE_OR_OTHER_CONTAINER_CHANGED")
                    if storage_before is not None and storage() != storage_before:
                        raise apps.AppError("STORAGE_RESPONSE_CHANGED")
                    print("CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS", flush=True)
                except (apps.AppError, ValueError, KeyError):
                    failure = "CORE_STORAGE_READBACK"
    print("VERIFY=" + ("FAIL" if failure else "PASS"))
    print("ERROR=" + ("APP_SMOKE_" + failure if failure else "NONE"))
    print("EXIT_CODE=" + ("1" if failure else "0"))
    print("PROJECT_END=Gserver\n========== GACE_RESULT_END ==========", flush=True)
    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
