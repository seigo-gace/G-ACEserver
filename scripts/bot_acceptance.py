"""Local Bot acceptance over the actual loopback port; no remote PASS claims."""
import hashlib
import json
import subprocess
import urllib.error
import urllib.request
import uuid

from gserverctl import ROOT, LOOPBACK_PORT


def request(path, token=None, value=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        f"http://127.0.0.1:{LOOPBACK_PORT}" + path,
        data=json.dumps(value).encode() if value is not None else None,
        headers=headers)
    # Do not send local credentials through proxy environment variables.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        response = client.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read(65536))


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def verify(control):
    release = control.load()
    result = control.run(["inspect", "--format", "{{json .}}",
                          "gace-gserver-gserver-1"], capture=True)
    info = json.loads(result.stdout)
    require(info["Image"] == release["current"], "BOT_IMAGE_MISMATCH")
    bindings = info["NetworkSettings"]["Ports"]
    require(bindings == {"8765/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(LOOPBACK_PORT)}]},
            "BOT_LOOPBACK_BINDING_MISMATCH")
    # Compare the imported application modules with the exact built runtime.
    names = ("gserver.py", "storage.py", "kb_source.py", "tgs_bridge.py")
    script = ("import pathlib,hashlib,json; print(json.dumps({n:hashlib.sha256("
              "(pathlib.Path('/opt/gserver/app')/n).read_bytes()).hexdigest() for n in "
              + repr(names) + "}))")
    result = control.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)
    expected = {n: hashlib.sha256((ROOT / "app" / n).read_bytes()).hexdigest() for n in names}
    require(json.loads(result.stdout) == expected, "BOT_RUNTIME_SOURCE_MISMATCH")

    # Values stay in this process, never argv, output, receipts or Git.
    script = (
        "import pathlib,json,os,stat\n"
        "values=[]\n"
        "for name in ('bot-auth-token','auth-token'):\n"
        " p=pathlib.Path('/var/lib/gserver')/name\n"
        " s=p.lstat()\n"
        " assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_mode & 0o077==0\n"
        " assert 32<=s.st_size<=4096\n"
        " values.append(p.read_text().strip())\n"
        "print(json.dumps(values))\n")
    result = control.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)
    bot_token, owner_token = json.loads(result.stdout)
    require(bot_token != owner_token, "BOT_OWNER_CREDENTIALS_NOT_SEPARATE")
    event = {"bot": "gserver-probe", "event_id": "accept-" + uuid.uuid4().hex,
             "event": "bot.started", "level": "info", "outcome": "PASS"}
    require(request("/health")[0] == 200, "BOT_HOST_HEALTH_FAILED")
    for token in (None, owner_token):
        require(request("/bot/events", token, event)[0] == 401, "BOT_AUTH_BOUNDARY_FAILED")
    require(request("/bot/queue", bot_token)[0] == 401, "BOT_OWNER_BOUNDARY_FAILED")
    require(request("/bot/queue", owner_token)[0] == 200, "BOT_OWNER_QUEUE_FAILED")
    status, body = request("/bot/events", bot_token, event)
    require(status == 202 and body.get("status") == "queued", "BOT_HOST_ENQUEUE_FAILED")

    def replay():
        status, body = request("/bot/events", bot_token, event)
        require(status == 202 and body.get("status") == "duplicate", "BOT_REPLAY_FAILED")
        require(request("/bot/events", bot_token, dict(event, outcome="SKIP"))[0] == 409,
                "BOT_CONFLICT_FAILED")

    def persisted():
        key = "gserver:gserver-probe:" + event["event_id"]
        script = (
            "import sqlite3,json,hashlib\n"
            "with sqlite3.connect('file:/var/lib/gserver/bot-spool/bot-events.sqlite3?mode=ro',uri=True) as c:\n"
            " rows=c.execute('SELECT fingerprint,payload FROM events WHERE id=?',(" + repr(key) + ",)).fetchall()\n"
            " assert len(rows)==1\n"
            " print(hashlib.sha256(json.dumps(rows).encode()).hexdigest())\n")
        return control.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script],
                           capture=True).stdout.strip()

    replay()
    before = persisted()
    require(len(before) == 64, "BOT_SQLITE_RECEIPT_INVALID")
    # Only the already owned Gserver project; always attempt to start it again.
    try:
        control.action("stop")
    finally:
        control.action("start")
    replay()
    require(persisted() == before, "BOT_SQLITE_RESTART_MISMATCH")
    print("BOT_HOST_AUTH_REPLAY_CONFLICT=PASS")
    print("BOT_SQLITE_STOP_START_PERSISTENCE=PASS")
    print("BOT_RUNTIME_SOURCE_MATCH=PASS")
    print("BOT_CORRELATION_EVENT=" + event["event_id"])
    return event["event_id"]
