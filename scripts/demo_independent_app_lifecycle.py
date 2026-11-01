#!/usr/bin/env python3
"""One synthetic app project: lifecycle update and compose rollback on the Core image."""
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


def probe_config(image, revision):
    token = secrets.token_hex(8)
    return {
        "services": {
            "web": {
                "image": image,
                "network_mode": "none",
                "restart": "no",
                "user": "65534:65534",
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "mem_limit": "64m",
                "logging": {"driver": "local", "options": {"max-size": "1m", "max-file": "2"}},
                "volumes": [{"type": "volume", "source": "data", "target": "/var/lib/gserver"}],
                "command": [
                    "python3",
                    "-u",
                    "-c",
                    "from pathlib import Path; import time; "
                    f"p=Path('/var/lib/gserver/demo'); p.write_text('{token}') if not p.exists() else None; "
                    "time.sleep(3600)",
                ],
                "healthcheck": {
                    "test": ["CMD", "python3", "-c", "from pathlib import Path; assert Path('/var/lib/gserver/demo').is_file()"],
                    "interval": "1s",
                    "timeout": "2s",
                    "retries": 15,
                },
                "labels": {"gserver.demo.revision": revision},
            }
        },
        "volumes": {"data": {}},
    }, token


def main():
    name = "demo-" + secrets.token_hex(4)
    phase = "PRECHECK"
    print("========== GACE_RESULT_BEGIN ==========", flush=True)
    print("PROJECT=Gserver\nACTION=INDEPENDENT_APP_LIFECYCLE_DEMO", flush=True)
    with tempfile.TemporaryDirectory(prefix="gserver-app-demo-") as directory:
        compose = Path(directory) / "compose.json"
        try:
            if apps.os.geteuid() != 0:
                apps.run(["sudo", "-n", "true"])
            core = json.loads(docker("inspect", CORE))[0]
            if core["State"].get("Health", {}).get("Status") != "healthy":
                raise apps.AppError("CORE_NOT_HEALTHY")
            image = core["Image"]
            if not apps.re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                raise apps.AppError("CORE_IMAGE_INVALID")

            def write_cfg(revision):
                cfg, _ = probe_config(image, revision)
                compose.write_text(json.dumps(cfg))

            def run(action):
                with contextlib.redirect_stdout(io.StringIO()):
                    apps.execute(action, compose, name)

            phase = "VERIFY_START"
            write_cfg("1")
            run("verify")
            run("start")

            phase = "RESTART"
            run("restart")

            phase = "UPDATE"
            write_cfg("2")
            run("start")
            cid = apps.run(apps.command(compose, name) + ["ps", "-q", "web"]).strip()
            row = json.loads(docker("inspect", cid))[0]
            if row["Config"]["Labels"].get("gserver.demo.revision") != "2":
                raise apps.AppError("APP_UPDATE_FAILED")

            phase = "ROLLBACK"
            write_cfg("1")
            run("start")
            row = json.loads(docker("inspect", apps.run(apps.command(compose, name) + ["ps", "-q", "web"]).strip()))[0]
            if row["Config"]["Labels"].get("gserver.demo.revision") != "1":
                raise apps.AppError("APP_ROLLBACK_FAILED")

            phase = "STOP"
            run("stop")
            print("APP_LIFECYCLE_DEMO=PASS", flush=True)
        except apps.AppError as exc:
            print("APP_FAILURE_DETAIL=" + str(exc), flush=True)
            print("VERIFY=FAIL", flush=True)
            print("ERROR=APP_DEMO_" + phase, flush=True)
            print("EXIT_CODE=1", flush=True)
            print("PROJECT_END=Gserver\n========== GACE_RESULT_END ==========", flush=True)
            return 1
        finally:
            with contextlib.suppress(apps.AppError):
                apps.run(apps.command(compose, name) + ["down", "--volumes", "--timeout", "10"])
    print("VERIFY=PASS", flush=True)
    print("ERROR=NONE", flush=True)
    print("EXIT_CODE=0", flush=True)
    print("PROJECT_END=Gserver\n========== GACE_RESULT_END ==========", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
