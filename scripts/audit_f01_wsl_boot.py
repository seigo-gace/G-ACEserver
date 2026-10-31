#!/usr/bin/env python3
"""Read-only F01 audit for WSL systemd boot and Docker stack; no install or restart."""
import json
import os
import subprocess
from pathlib import Path

WSL_CONF = Path("/etc/wsl.conf")


def read_wsl_conf():
    result = {"present": WSL_CONF.is_file(), "boot_systemd": "NOT_CONFIGURED"}
    if not result["present"]:
        return result
    try:
        text = WSL_CONF.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result["read_error"] = type(exc).__name__
        return result
    section = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section == "boot" and "=" in line:
            key, _, value = line.partition("=")
            if key.strip().lower() == "systemd":
                result["boot_systemd"] = value.strip().lower()
    return result


def unit_state(unit):
    out = {"unit": unit, "is_enabled": "UNKNOWN", "is_active": "UNKNOWN"}
    for field, args in (("is_enabled", ["is-enabled"]), ("is_active", ["is-active"])):
        try:
            proc = subprocess.run(
                ["systemctl", *args, unit],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out[field] = (proc.stdout or proc.stderr).strip() or "UNKNOWN"
        except (OSError, subprocess.TimeoutExpired):
            out[field] = "UNAVAILABLE"
    return out


def docker_cmd():
    return ["docker"] if os.geteuid() == 0 else ["sudo", "-n", "docker"]


def docker_summary():
    try:
        proc = subprocess.run(
            docker_cmd() + ["info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return {"reachable": True, "server_version": proc.stdout.strip()}
        return {"reachable": False, "error": (proc.stderr or proc.stdout).strip()[:200]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"reachable": False, "error": type(exc).__name__}


def compose_version():
    for cmd in (docker_cmd() + ["compose", "version", "--short"],):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                return {"available": True, "version": proc.stdout.strip()}
        except (OSError, subprocess.TimeoutExpired):
            continue
    return {"available": False}


def audit():
    wsl = read_wsl_conf()
    docker = docker_summary()
    compose = compose_version()
    services = [unit_state(name) for name in ("docker.service", "containerd.service")]
    units_active = all(item.get("is_active") == "active" for item in services)
    systemd_boot = wsl.get("boot_systemd") == "true"
    partial = systemd_boot and docker.get("reachable") and units_active
    return {
        "scope": "f01_wsl_boot_read_only",
        "wsl_conf": wsl,
        "docker": docker,
        "compose": compose,
        "systemd_units": services,
        "wsl_systemd_boot_configured": systemd_boot,
        "docker_stack_running": bool(docker.get("reachable")) and units_active,
        "windows_autostart_to_wsl": "NOT_VERIFIED",
        "windows_reboot_recovery": "NOT_VERIFIED",
        "f01_partial_wsl_layer": "PASS" if partial else "NOT_VERIFIED",
    }


def main():
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=F01_WSL_BOOT_READ_ONLY_AUDIT")
    exit_code = 1
    try:
        payload = audit()
        print("WSL_SYSTEMD_BOOT_CONFIGURED=" + str(payload["wsl_systemd_boot_configured"]))
        print("DOCKER_STACK_RUNNING=" + str(payload["docker_stack_running"]))
        print("WINDOWS_AUTOSTART_TO_WSL=" + payload["windows_autostart_to_wsl"])
        print("WINDOWS_REBOOT_RECOVERY=" + payload["windows_reboot_recovery"])
        print("F01_PARTIAL_WSL_LAYER=" + payload["f01_partial_wsl_layer"])
        print(
            "AUDIT_JSON="
            + json.dumps(
                {key: value for key, value in payload.items() if key != "scope"},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        print("CHANGES=NONE")
        exit_code = 0 if payload["f01_partial_wsl_layer"] == "PASS" else 1
        print("VERIFY=" + ("PASS" if exit_code == 0 else "FAIL"))
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
