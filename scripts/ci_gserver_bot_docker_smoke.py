#!/usr/bin/env python3
"""Isolated real-container Bot delivery/spool smoke for Gserver CI.

Uses a disposable Docker named volume, no published ports or external network.
Does not connect to Gateway/TGserver or read existing owner PC credentials.
"""
import os
import secrets
import subprocess
import sys
import time

IMAGE = "gace-gserver:ci"

INSIDE = r'''
import json
import os
from pathlib import Path
import sqlite3
import sys
import urllib.error
import urllib.request

phase = sys.argv[1]
root = Path("/var/lib/gserver")
owner_file, bot_file = root / "auth-token", root / "bot-auth-token"
if phase == "first":
    for path in (owner_file, bot_file):
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            import secrets
            with os.fdopen(fd, "w") as stream:
                stream.write(secrets.token_hex(32))
        except BaseException:
            os.close(fd)
            raise

owner, bot = owner_file.read_text(), bot_file.read_text()
assert owner != bot and len(owner) >= 32 and len(bot) >= 32
client = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def fetch(method, path, credential=None, value=None):
    headers = {"Content-Type": "application/json"}
    if credential is not None:
        headers["Authorization"] = "Bearer " + credential
    request = urllib.request.Request(
        "http://127.0.0.1:8765" + path,
        data=json.dumps(value).encode("utf-8") if value is not None else None,
        headers=headers, method=method)
    try:
        response = client.open(request, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read(65536))

event = {"bot": "gserver-ci", "event_id": "ci-event-1", "event": "bot.started",
         "level": "info", "outcome": "PASS"}
assert fetch("GET", "/health")[0] == 200
if phase == "first":
    assert fetch("POST", "/bot/events", None, event)[0] == 401
    assert fetch("POST", "/bot/events", owner, event)[0] == 401
    assert fetch("GET", "/bot/queue", bot)[0] == 401
    status, body = fetch("POST", "/bot/events", bot, event)
    assert status == 202 and body.get("status") == "queued", (status, body)
status, body = fetch("POST", "/bot/events", bot, event)
assert status == 202 and body.get("status") == "duplicate", (status, body)
assert fetch("POST", "/bot/events", bot, dict(event, outcome="SKIP"))[0] == 409
status, info = fetch("GET", "/bot/queue", owner)
assert status == 200, (status, info)
db = root / "bot-spool" / "bot-events.sqlite3"
assert db.is_file()
with sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True) as conn:
    rows = conn.execute("SELECT state,payload FROM events WHERE id=?",
                        ("gserver:gserver-ci:ci-event-1",)).fetchall()
    assert len(rows) == 1 and rows[0][0] in ("pending", "sending", "sent")
print("BOT_DOCKER_" + phase.upper() + "=PASS")
'''

def run(*args, step="docker", timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        # Do not echo owner credentials, environment or complete host diagnostics.
        raise RuntimeError(f"{step}: exit={result.returncode}; "
                           f"stderr={result.stderr[-1600:]}")
    return result.stdout.strip()


def inside(name, phase):
    return run("docker", "exec", name, "python3", "-B", "-c", INSIDE, phase,
               step="BOT_" + phase, timeout=15)


def main():
    suffix = secrets.token_hex(6)
    volume, name = "gserver-ci-bot-" + suffix, "gserver-ci-bot-" + suffix
    created = False
    try:
        run("docker", "volume", "create", volume, step="volume_create")
        created = True
        run("docker", "run", "-d", "--name", name, "--network", "none",
            "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "64",
            "--memory", "256m", "--cpus", "0.50",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16m,uid=65534,gid=65534,mode=0700",
            "--mount", "type=volume,source=" + volume + ",target=/var/lib/gserver",
            "-e", "GSERVER_BOT_SPOOL_DIR=/var/lib/gserver/bot-spool",
            "-e", "GSERVER_BOT_AUTH_FILE=/var/lib/gserver/bot-auth-token",
            "-e", "GSERVER_AUTH_FILE=/var/lib/gserver/auth-token",
            IMAGE, step="docker_run")
        for _ in range(30):
            check = subprocess.run(
                ("docker", "exec", name, "python3", "-B", "-c",
                 "import urllib.request; assert urllib.request.urlopen("
                 "'http://127.0.0.1:8765/health',timeout=2).status==200"),
                capture_output=True, timeout=5)
            if check.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("bot container did not become healthy")
        print(inside(name, "first"))
        run("docker", "restart", name, step="docker_restart")
        print(inside(name, "restart"))
        print("BOT_DOCKER_PERSISTENCE_AUTH_CONFLICT=PASS")
    finally:
        subprocess.run(("docker", "rm", "-f", name), capture_output=True, timeout=30)
        if created:
            subprocess.run(("docker", "volume", "rm", volume), capture_output=True, timeout=30)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print("BOT_DOCKER_SMOKE=FAIL;CAUSE=" + str(error), file=sys.stderr)
        sys.exit(1)
