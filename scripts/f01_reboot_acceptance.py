#!/usr/bin/env python3
"""Capture and compare read-only F01 Windows/WSL reboot evidence.

The command never reboots Windows, starts/stops a service, or changes Docker.
It writes only an owner-private evidence snapshot when ``capture`` is selected.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import audit_f01_wsl_boot


SCHEMA = "gserver.f01-reboot-evidence.v1"
DEFAULT_EVIDENCE = (
    Path.home() / ".local" / "state" / "gserver" / "verification" / "f01-reboot-before.json"
)
WSL_BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
CORE_HEALTH_URL = "http://127.0.0.1:18765/health"
CORE_CONTAINER = "gace-gserver-gserver-1"


class EvidenceError(RuntimeError):
    """The evidence cannot support an acceptance decision."""


def _run(command: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def windows_boot_id() -> str:
    command = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')",
    ]
    try:
        proc = _run(command, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("WINDOWS_BOOT_ID_UNAVAILABLE") from exc
    value = proc.stdout.strip()
    if proc.returncode != 0 or not value:
        raise EvidenceError("WINDOWS_BOOT_ID_UNAVAILABLE")
    return value


def wsl_boot_id() -> str:
    try:
        value = WSL_BOOT_ID.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise EvidenceError("WSL_BOOT_ID_UNAVAILABLE") from exc
    if not value:
        raise EvidenceError("WSL_BOOT_ID_UNAVAILABLE")
    return value


def core_container() -> dict:
    command = audit_f01_wsl_boot.docker_cmd() + [
        "inspect",
        "--format",
        "{{.Id}}|{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        CORE_CONTAINER,
    ]
    try:
        proc = _run(command)
    except (OSError, subprocess.TimeoutExpired):
        return {"present": False, "state": "UNAVAILABLE", "health": "UNAVAILABLE"}
    parts = proc.stdout.strip().split("|", 2)
    if proc.returncode != 0 or len(parts) != 3:
        return {"present": False, "state": "UNAVAILABLE", "health": "UNAVAILABLE"}
    return {"present": True, "id": parts[0], "state": parts[1], "health": parts[2]}


def core_health() -> dict:
    request = urllib.request.Request(CORE_HEALTH_URL, headers={"User-Agent": "gserver-f01-audit/1"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            status = response.status
    except Exception as exc:  # urllib exposes several transport exception types
        return {"reachable": False, "error": type(exc).__name__}
    valid = status == 200 and '"status":"ok"' in body.replace(" ", "")
    return {"reachable": valid, "http_status": status}


def capture_snapshot() -> dict:
    audit = audit_f01_wsl_boot.audit()
    return {
        "schema": SCHEMA,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows_boot_id": windows_boot_id(),
        "wsl_boot_id": wsl_boot_id(),
        "wsl_audit": {
            "wsl_systemd_boot_configured": audit["wsl_systemd_boot_configured"],
            "docker_stack_running": audit["docker_stack_running"],
            "f01_partial_wsl_layer": audit["f01_partial_wsl_layer"],
        },
        "core_container": core_container(),
        "core_health": core_health(),
    }


def write_private_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".f01-reboot-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_evidence(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file():
            raise EvidenceError("BEFORE_EVIDENCE_NOT_REGULAR")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("BEFORE_EVIDENCE_INVALID") from exc
    if payload.get("schema") != SCHEMA:
        raise EvidenceError("BEFORE_EVIDENCE_SCHEMA_MISMATCH")
    for key in ("windows_boot_id", "wsl_boot_id", "captured_at_utc"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise EvidenceError("BEFORE_EVIDENCE_INCOMPLETE")
    return payload


def compare(before: dict, after: dict) -> dict:
    windows_changed = before["windows_boot_id"] != after["windows_boot_id"]
    wsl_changed = before["wsl_boot_id"] != after["wsl_boot_id"]
    stack_running = after["wsl_audit"]["f01_partial_wsl_layer"] == "PASS"
    container_ready = (
        after["core_container"].get("state") == "running"
        and after["core_container"].get("health") == "healthy"
    )
    health_ready = after["core_health"].get("reachable") is True
    accepted = windows_changed and wsl_changed and stack_running and container_ready and health_ready
    return {
        "windows_boot_changed": windows_changed,
        "wsl_boot_changed": wsl_changed,
        "docker_stack_recovered": stack_running,
        "gserver_container_recovered": container_ready,
        "gserver_health_recovered": health_ready,
        "windows_reboot_recovery": "PASS" if accepted else "NOT_VERIFIED",
        # Running this comparison may itself start WSL, so it cannot prove automatic launch.
        "windows_autostart_to_wsl": "NOT_VERIFIED",
        "verify": "PASS" if accepted else "FAIL",
    }


def emit(payload: dict, action: str) -> int:
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print(f"ACTION={action}")
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            continue
        print(f"{key.upper()}={value}")
    print("EVIDENCE_JSON=" + json.dumps(payload, separators=(",", ":"), sort_keys=True))
    print("CHANGES=PRIVATE_EVIDENCE_ONLY" if action.endswith("CAPTURE") else "CHANGES=NONE")
    print("PROJECT_END=Gserver")
    print("========== GACE_RESULT_END ==========")
    return 0 if payload.get("verify") == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "compare"))
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args(argv)
    try:
        if args.action == "capture":
            snapshot = capture_snapshot()
            write_private_json(args.evidence, snapshot)
            return emit(
                {
                    "evidence_path": str(args.evidence),
                    "snapshot_ready": True,
                    "windows_reboot_recovery": "NOT_VERIFIED",
                    "windows_autostart_to_wsl": "NOT_VERIFIED",
                    "verify": "PASS",
                },
                "F01_REBOOT_EVIDENCE_CAPTURE",
            )
        before = load_evidence(args.evidence)
        after = capture_snapshot()
        return emit(compare(before, after), "F01_REBOOT_RECOVERY_COMPARE")
    except EvidenceError as exc:
        return emit(
            {
                "error": str(exc),
                "windows_reboot_recovery": "NOT_VERIFIED",
                "windows_autostart_to_wsl": "NOT_VERIFIED",
                "verify": "FAIL",
            },
            "F01_REBOOT_" + args.action.upper(),
        )


if __name__ == "__main__":
    raise SystemExit(main())
