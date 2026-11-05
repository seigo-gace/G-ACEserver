#!/usr/bin/env python3
"""Explicit owner-initiated Gserver Bot-ready local acceptance.

Runs tests -> bounded Docker preflight -> immutable image build -> existing
gserverctl safe activation -> loopback-only access -> bot token -> local smoke.
Does NOT configure live Gateway secrets or claim a real Telegram delivery.
"""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gserverctl import Controller, STATE

MIN_AVAILABLE_BYTES = 2 * 1024 ** 3


def run_tests():
    for pattern in ("test_tgs_bridge.py", "test_runtime.py", "test_gserver_bot_ready_contract.py", "test_bot_acceptance.py"):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
             "-p", pattern, "-q"], cwd=ROOT, check=False, timeout=180)
        if result.returncode:
            raise RuntimeError("BOT_LOCAL_TESTS_FAILED_" + pattern.replace(".", "_"))
    print("BOT_LOCAL_TESTS=PASS")


def docker_preflight(controller):
    try:
        reported = controller.run(["info", "--format", "{{.DockerRootDir}}"], capture=True)
    except subprocess.CalledProcessError as error:
        # Do not echo daemon output, command arguments or private configuration.
        if "password is required" in (error.stderr or ""):
            raise RuntimeError("DOCKER_SUDO_AUTH_REQUIRED") from None
        raise RuntimeError("DOCKER_LOCAL_ACCESS_FAILED") from None
    docker_root = Path(reported.stdout.strip())
    if not docker_root.is_absolute() or not docker_root.is_dir() or docker_root.is_symlink():
        raise RuntimeError("DOCKER_ROOT_UNKNOWN")
    # Check both the actual image store and containerd placement before a build.
    directories = (docker_root, Path("/var/lib/containerd"))
    checked = 0
    for path in directories:
        if path.is_dir():
            stat = os.statvfs(path)
            available = stat.f_bavail * stat.f_frsize
            if available < MIN_AVAILABLE_BYTES:
                raise RuntimeError("DOCKER_STORAGE_HEADROOM_LOW")
            checked += 1
    if checked == 0:
        raise RuntimeError("DOCKER_STORAGE_LAYOUT_UNKNOWN")
    print("DOCKER_PREFLIGHT=PASS")


def install():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(STATE / "operation.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        control = Controller()
        docker_preflight(control)
        # Never replace an unowned Compose deployment or touch the existing
        # legacy Gserver prototype on 127.0.0.1:8765.
        control.run(["build", "--pull=false", "--tag", "gace-gserver:bot-ready-local",
                     "--file", str(ROOT / "Dockerfile"), str(ROOT)])
        inspected = control.run(["image", "inspect", "gace-gserver:bot-ready-local",
                                "--format", "{{.Id}}"], capture=True)
        image = inspected.stdout.strip()
        if not image.startswith("sha256:") or len(image) != 71:
            raise RuntimeError("BUILT_IMAGE_ID_INVALID")
        release = control.load()
        if release.get("current") != image:
            control.activate(image)
        if control.load().get("access") != "loopback":
            control.action("enable-local")
        try:
            control.action("bot-init")
            control.ensure_token()
            control.action("bot-smoke")
            from bot_acceptance import verify
            verify(control)
            control.action("bot-status")
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError):
            # Activation health alone cannot accept a broken Bot release.
            # Restore the prior image AND access/storage profile; retain volumes.
            if release.get("current"):
                control.activate(release["current"],
                                 access=release.get("access", "isolated"),
                                 storage=release.get("storage", False))
                control.save(release)
                print("BOT_ACCEPTANCE_ROLLBACK=PREVIOUS_RELEASE_RESTORED")
            else:
                control.action("stop")
                print("BOT_ACCEPTANCE_ROLLBACK=NEW_INSTALL_STOPPED_VOLUME_RETAINED")
            raise
    print("BOT_GSERVER_LOCAL=PASS")
    print("BOT_GATEWAY_REMOTE=NOT_VERIFIED")
    print("TGSERVER_TELEGRAM_RAW_SEARCH=NOT_VERIFIED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true",
                        help="Explicitly permit Docker build and Gserver activation")
    args = parser.parse_args()
    print("========== GACE_RESULT_BEGIN ==========", flush=True)
    print("PROJECT=Gserver")
    print("ACTION=BOT_READY_LOCAL_ACCEPTANCE")
    try:
        run_tests()
        if args.install:
            install()
            print("VERIFY=PASS")
        else:
            print("BOT_DEPLOYMENT=SKIPPED_EXPLICIT_INSTALL_REQUIRED")
            print("VERIFY=SOURCE_TESTS_PASS_ONLY")
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print("FAILED_PHASE_ERROR=" + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        print("BOT_GSERVER_LOCAL=NOT_VERIFIED")
        print("VERIFY=FAIL")
        return 1
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")


if __name__ == "__main__":
    raise SystemExit(main())
