#!/usr/bin/env python3
"""Quick operational gate for the shared Gserver ServerTerminal (no secrets printed)."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("GSERVER_TERMINAL_STATE", "/home/gace/.local/state/gserver-terminal"))
PUBLIC_HEALTH = os.environ.get("GSERVER_TERMINAL_PUBLIC_HEALTH", "https://gserver-terminal.asterav8.jp/healthz")
LOCAL_HEALTH = "http://127.0.0.1:8790/healthz"
SERVICES = ("gserver-terminal-host.service", "gserver-terminal-cloudflared.service")


def shlex_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def run(argv, timeout=30):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def health(url):
    proc = run(["curl", "-fsS", "--max-time", "10", url], timeout=15)
    if proc.returncode:
        return False
    try:
        return json.loads(proc.stdout).get("ok") is True
    except (ValueError, json.JSONDecodeError):
        return False


def gateway_roundtrip():
    env_file = Path("/home/gace/.config/gserver-terminal-host/env")
    if not env_file.is_file():
        return "SKIP", "env missing"
    server_core = Path("/home/gace/server-core")
    send = server_core / "scripts/servercore_bounded_host_gateway_send.py"
    if not send.is_file():
        return "SKIP", "server-core send script missing"
    sc_sha = run(["git", "-C", str(server_core), "rev-parse", "HEAD"]).stdout.strip()
    gs_sha = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout.strip()
    if len(sc_sha) != 40 or len(gs_sha) != 40:
        return "FAIL", "git head unavailable"
    cmd = "printf GSERVER_OPERATIONAL_GATEWAY_OK\\n"
    shell = (
        f"set -a && source {shlex_quote(env_file)} && set +a && "
        f"python3 {shlex_quote(send)} --command-id host.command "
        f"--expected-sha {sc_sha} --repository seigo-gace/G-ACEserver "
        f"--repo-sha {gs_sha} --host-target gserver "
        f"--host-command {shlex_quote(cmd)}"
    )
    proc = run(["bash", "-lc", shell], timeout=90)
    if proc.returncode:
        return "FAIL", (proc.stderr or proc.stdout or "gateway send failed").strip()[:120]
    tail = [ln for ln in (proc.stdout or "").splitlines() if ln.startswith("{")]
    try:
        rid = json.loads(tail[-1]).get("request_id")
    except (IndexError, json.JSONDecodeError):
        return "FAIL", "no request_id"
    if not isinstance(rid, str):
        return "FAIL", "request_id missing"
    result_path = STATE / "results" / f"{rid}.json"
    for _ in range(30):
        if result_path.is_file():
            record = json.loads(result_path.read_text(encoding="utf-8"))
            result = record.get("result") or {}
            if result.get("state") == "PASS" and result.get("exit_code") == 0:
                return "PASS", rid
            if record.get("state") == "COMPLETED":
                return "FAIL", f"{rid} exit={result.get('exit_code')}"
        time.sleep(1)
    return "FAIL", f"{rid} timeout"


def main():
    report = {"services": {}, "health_local": False, "health_public": False, "gateway": "SKIP"}
    ok = True
    for unit in SERVICES:
        active = run(["systemctl", "--user", "is-active", unit]).stdout.strip() == "active"
        report["services"][unit] = active
        ok = ok and active
    report["health_local"] = health(LOCAL_HEALTH)
    report["health_public"] = health(PUBLIC_HEALTH)
    ok = ok and report["health_local"]
    gw_state, gw_detail = gateway_roundtrip()
    report["gateway"] = gw_state
    report["gateway_detail"] = gw_detail
    if gw_state == "FAIL":
        ok = False
    print("GSERVER_TERMINAL_OPERATIONAL=" + ("PASS" if ok else "FAIL"))
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())