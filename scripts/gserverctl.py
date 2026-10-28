#!/usr/bin/env python3
"""Offline lifecycle for the dedicated Gserver Compose project; never deletes data."""
import argparse
import fcntl
import hashlib
import getpass
import urllib.parse
import json
import os
from pathlib import Path
import re
import stat
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "gserver"
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
LOOPBACK_PORT = 18765
STORAGE_DRIVE = Path("/mnt/g")
STORAGE_HOST = STORAGE_DRIVE / "GserverStorage"

def prepare_storage(drive=STORAGE_DRIVE):
    """Make only the dedicated data subtree, without following existing links."""
    if not os.path.ismount(drive):
        raise ValueError("G drive not mounted; refusing storage activation")
    fd = os.open(drive, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    device = os.fstat(fd).st_dev
    try:
        for component in ("GserverStorage", "files"):
            try:
                os.mkdir(component, mode=0o755, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            if os.fstat(child).st_dev != device:
                os.close(child)
                raise ValueError("storage path crosses a mount")
            os.close(fd)
            fd = child
    finally:
        os.close(fd)



class Controller:
    def __init__(self, state=STATE, project="gace-gserver"):
        if project != "gace-gserver" and not re.fullmatch(r"gace-gserver-test-[a-f0-9]{16}", project):
            raise ValueError("invalid project")
        self.project = project
        self.state = state
        self.record = state / "releases.json"
        self.pending = state / "pending.json"
        self.docker = (["docker"] if os.geteuid() == 0 else ["sudo", "-n", "docker"]) + ["--host", "unix:///var/run/docker.sock"]

    def bundle(self, image, create=False, access="isolated", storage=False):
        if not isinstance(image, str) or not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        if access not in ("isolated", "loopback"):
            raise ValueError("invalid access profile")
        if not isinstance(storage, bool) or (storage and access != "loopback"):
            raise ValueError("storage needs local-only access")
        directory = self.state / "bundles"
        manifest = directory / (image[7:] + (".storage-ro-v1.json" if storage else ".loopback-v2.json" if access == "loopback" else ".json"))
        if create and not manifest.exists():
            source = (ROOT / "deploy/compose.gserver.yaml").read_text()
            source = source.replace("${GSERVER_IMAGE:?immutable_image_required}", image)
            if access == "loopback":
                marker = "    network_mode: none\n"
                if source.count(marker) != 1:
                    raise ValueError("unexpected base network contract")
                source = source.replace(marker,
                    '    ports:\n      - "127.0.0.1:18765:8765"\n'
                    '    networks:\n      - gserver-local-v2\n', 1)
                source += "\nnetworks:\n  gserver-local-v2:\n    driver: bridge\n"
            if storage:
                marker = "    volumes:\n      - state:/var/lib/gserver\n"
                if source.count(marker) != 1:
                    raise ValueError("unexpected volume contract")
                mount = (
                    "      - type: bind\n"
                    "        source: /mnt/g/GserverStorage\n"
                    "        target: /mnt/g\n"
                    "        read_only: true\n"
                    "        bind:\n"
                    "          create_host_path: false\n"
                )
                source = source.replace(marker, marker + mount, 1)
                extra = (
                    "      GSERVER_STORAGE_ROOT: /mnt/g\n"
                    "      GSERVER_FILES_ROOT: /mnt/g/files\n"
                    "      GSERVER_AUTH_FILE: /var/lib/gserver/auth-token\n"
                )
                marker_env = "    environment:\n"
                if source.count(marker_env) != 1:
                    raise ValueError("unexpected environment contract")
                source = source.replace(marker_env, marker_env + extra, 1)
            if "$" in source:
                raise ValueError("unresolved deployment variables")
            directory.mkdir(mode=0o700, exist_ok=True)
            digest = hashlib.sha256(source.encode()).hexdigest()
            target = directory / (digest + ".yaml")
            if not target.exists():
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(source)
                        stream.flush()
                        os.fsync(stream.fileno())
                    temporary.replace(target)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("deployment snapshot changed")
            self.write_atomic(manifest, {"sha256": digest})
        data = json.loads(manifest.read_text())
        digest = data.get("sha256") if isinstance(data, dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid deployment manifest")
        target = directory / (digest + ".yaml")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("deployment snapshot changed")
        return target

    def run(self, args, capture=False, env=None):
        return subprocess.run(self.docker + args, check=True, text=True,
                              capture_output=capture, timeout=180, env=env)

    def load(self):
        if not self.record.exists():
            return {}
        data = json.loads(self.record.read_text())
        if not isinstance(data, dict) or (data and 'current' not in data) or any(
            (k in ("current", "previous") and (not isinstance(v, str) or not IMAGE.fullmatch(v))) or
            (k == "access" and v != "loopback") or
            (k == "storage" and v is not True) or k not in ("current", "previous", "access", "storage")
            for k, v in data.items()
        ):
            raise ValueError("invalid release record")
        if data.get("storage") and data.get("access") != "loopback":
            raise ValueError("storage requires local-only access")
        return data

    def write_atomic(self, target, data):
        temporary = target.with_suffix(".tmp")
        with open(temporary, "w") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def save(self, data):
        self.write_atomic(self.record, data)

    def recover(self):
        if not self.pending.exists():
            raise ValueError("no interrupted operation")
        pending = json.loads(self.pending.read_text())
        if not isinstance(pending, dict):
            raise ValueError("invalid pending record")
        target = pending.get("target", "")
        if not isinstance(target, str) or not IMAGE.fullmatch(target):
            raise ValueError("invalid pending image")
        release = self.load()
        if release.get("current"):
            self.compose(release["current"], ["up", "-d", "--wait", "--wait-timeout", "60"], release.get("access", "isolated"), release.get("storage", False))
        else:
            self.compose(target, ["stop", "--timeout", "10"])
        self.pending.unlink()

    def compose(self, image, args, access="isolated", storage=False):
        snapshot = self.bundle(image, access=access, storage=storage)
        # Image is literal in the snapshot: sudo environment filtering is irrelevant.
        return self.run(["compose", "--project-name", self.project, "--env-file", "/dev/null",
                         "--project-directory", str(self.state), "-f", str(snapshot), *args])

    def activate(self, image, access=None, storage=None):
        if self.pending.exists():
            raise ValueError("interrupted operation; run recover first")
        if not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        old = self.load()
        access = access or old.get("access", "isolated")
        storage = old.get("storage", False) if storage is None else storage
        if access not in ("isolated", "loopback") or (storage and access != "loopback"):
            raise ValueError("invalid access/storage profile")
        self.run(["image", "inspect", image], capture=True)
        self.bundle(image, create=True, access=access, storage=storage)
        if old.get("current"):
            self.bundle(old["current"], access=old.get("access", "isolated"), storage=old.get("storage", False))
        # First installation may not take over an existing project.
        if not old:
            existing = self.run(["ps", "-aq", "--filter",
                                 "label=com.docker.compose.project=" + self.project], capture=True)
            volumes = self.run(["volume", "ls", "-q", "--filter",
                                "label=com.docker.compose.project=" + self.project], capture=True)
            if existing.stdout.strip() or volumes.stdout.strip():
                raise ValueError("unowned Gserver project exists; inspect before adoption")
        self.write_atomic(self.pending, {"target": image, "access": access, "storage": storage})
        try:
            self.compose(image, ["up", "-d", "--force-recreate", "--wait", "--wait-timeout", "60"], access, storage)
        except (subprocess.SubprocessError, OSError):
            if old.get("current"):
                self.compose(old["current"], ["up", "-d", "--force-recreate", "--wait", "--wait-timeout", "60"], old.get("access", "isolated"), old.get("storage", False))
            else:
                self.compose(image, ["stop", "--timeout", "10"])
            self.pending.unlink()
            raise
        new = {"current": image}
        if access == "loopback":
            new["access"] = "loopback"
        if storage:
            new["storage"] = True
        if old.get("current") and old["current"] != image:
            new["previous"] = old["current"]
        elif old.get("previous"):
            new["previous"] = old["previous"]
        self.save(new)
        self.pending.unlink()

    def ensure_token(self):
        """Generate the API credential inside the existing persistent volume, no stdout."""
        script = (
            "import os,secrets,stat\n"
            "p='/var/lib/gserver/auth-token'\n"
            "try:\n"
            " f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n"
            "except FileExistsError:\n"
            " f=None\n"
            "if f is not None:\n"
            " try:\n"
            "  os.write(f,secrets.token_hex(32).encode())\n"
            "  os.fsync(f)\n"
            " finally:\n"
            "  os.close(f)\n"
            "s=os.stat(p,follow_symlinks=False)\n"
            "assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid()\n"
            "assert s.st_mode & 0o077 == 0 and 32<=s.st_size<=4096\n"
        )
        self.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)

    def bot_init(self):
        # Credential remains in the existing private Docker named volume.
        script = (
            "import os,secrets,stat\n"
            "p='/var/lib/gserver/bot-auth-token'\n"
            "try:\n"
            " f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n"
            "except FileExistsError:\n"
            " f=None\n"
            "if f is not None:\n"
            " try:\n"
            "  os.write(f,secrets.token_hex(32).encode())\n"
            "  os.fsync(f)\n"
            " finally:\n"
            "  os.close(f)\n"
            "s=os.stat(p,follow_symlinks=False)\n"
            "assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid()\n"
            "assert s.st_mode & 0o077 == 0 and 32<=s.st_size<=4096\n"
        )
        self.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)
        print("GSERVER_BOT_TOKEN=INITIALIZED_PRIVATE_NO_OUTPUT")

    def bot_retry(self):
        script = (
            "import sys\n"
            "sys.path.insert(0,'/opt/gserver/app')\n"
            "from tgs_bridge import BotSpool\n"
            "print('BOT_GATEWAY_RETRY_QUEUED='+str(BotSpool('/var/lib/gserver/bot-spool').retry_blocked(limit=100)))\n"
        )
        result = self.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)
        print(result.stdout.rstrip())

    def bot_status(self):
        script = (
            "import sys,json,os\n"
            "sys.path.insert(0,'/opt/gserver/app')\n"
            "from tgs_bridge import BotSpool\n"
            "p='/var/lib/gserver/bot-spool'\n"
            "if os.path.isdir(p):\n"
            " print('BOT_QUEUE='+json.dumps(BotSpool(p).counts(),sort_keys=True))\n"
            "else:\n"
            " print('BOT_QUEUE=NOT_INITIALIZED')\n"
            "print('GATEWAY_CONFIGURED='+str(os.path.isfile('/var/lib/gserver/gateway-url') and os.path.isfile('/var/lib/gserver/gateway-token')))\n"
        )
        result = self.run(["exec", "gace-gserver-gserver-1", "python3", "-c", script], capture=True)
        print(result.stdout.rstrip())

    def bot_smoke(self):
        script = (
            "import json,uuid,pathlib,urllib.request\n"
            "token=pathlib.Path('/var/lib/gserver/bot-auth-token').read_text().strip()\n"
            "value={'bot':'gserver-probe','event_id':'probe-'+uuid.uuid4().hex,'event':'bot.started','level':'info','outcome':'PASS'}\n"
            "body=json.dumps(value).encode()\n"
            "req=urllib.request.Request('http://127.0.0.1:8765/bot/events',data=body,method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})\n"
            "with urllib.request.urlopen(req,timeout=5) as response:\n"
            " assert response.status==202\n"
            " assert json.load(response)['queued'] is True\n"
            "print('BOT_EVENT_LOCAL_DURABLE_ACCEPT=PASS')\n"
        )
        result = self.run(["exec","gace-gserver-gserver-1","python3","-c",script],capture=True)
        print(result.stdout.rstrip())

    def bot_gateway_preflight(self, payload):
        """Check container HTTPS/auth and schema rejection before storing
        any credentials that would automatically release pending Bot events.
        The URL's private-network authorization is a separate operator gate.\n        The deliberately invalid request must be rejected BEFORE persistence.
        """
        probe = (
            "import json,sys,urllib.error,urllib.request\n"
            "sys.path.insert(0,'/opt/gserver/app')\n"
            "from tgs_bridge import _NoGatewayRedirect,gateway_endpoint\n"
            "value=json.load(sys.stdin)\n"
            "headers={'Content-Type':'application/json','Authorization':'Bearer '+value['token']}\n"
            "if bool(value.get('access_id'))!=bool(value.get('access_secret')):\n"
            " raise RuntimeError('GATEWAY_ACCESS_CREDS_INCOMPLETE')\n"
            "if value.get('access_id'):\n"
            " headers['CF-Access-Client-Id']=value['access_id']\n"
            " headers['CF-Access-Client-Secret']=value['access_secret']\n"
            "req=urllib.request.Request(gateway_endpoint(value['url']),data=b'{}',"
            "method='POST',headers=headers)\n"
            "client=urllib.request.build_opener(_NoGatewayRedirect())\n"
            "try:\n"
            " with client.open(req,timeout=5): pass\n"
            "except urllib.error.HTTPError as exc:\n"
            " if exc.code!=422: raise RuntimeError('GATEWAY_PREFLIGHT_REJECTED')\n"
            " try: answer=json.loads(exc.read(16384))\n"
            " except (ValueError,UnicodeError): raise RuntimeError('GATEWAY_PREFLIGHT_INVALID_RESPONSE')\n"
            " if not isinstance(answer,dict) or answer.get('error')!='invalid internal event':"
            " raise RuntimeError('GATEWAY_PREFLIGHT_WRONG_ENDPOINT')\n"
            "else: raise RuntimeError('GATEWAY_PREFLIGHT_ACCEPTED_INVALID_EVENT')\n"
            "print('GATEWAY_AUTH_SCHEMA_PREFLIGHT=PASS')\n"
        )
        result = subprocess.run(
            self.docker + ["exec", "-i", "gace-gserver-gserver-1", "python3", "-c", probe],
            input=payload, capture_output=True, text=True, timeout=15, check=True)
        if result.stdout.strip() != "GATEWAY_AUTH_SCHEMA_PREFLIGHT=PASS":
            raise ValueError("gateway preflight result not verified")
        print("GATEWAY_AUTH_SCHEMA_PREFLIGHT=PASS")

    def gateway_auth_inputs(self):
        # Never pass the private internal API token in CLI args, source or stdout.
        url = input("Gateway HTTPS base URL (/internal/events): ").strip()
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or
                parsed.path not in ("", "/", "/internal/events") or len(url) > 300):
            raise ValueError("invalid private Gateway HTTPS URL")
        token = getpass.getpass("Gateway INTERNAL_EVENT_API token (hidden): ")
        if not 24 <= len(token) <= 4096 or any(ord(c) <= 32 or ord(c) >= 127 for c in token):
            raise ValueError("invalid Gateway bearer token")
        access_id = getpass.getpass("Cloudflare Access Client ID (blank if not used): ")
        access_secret = getpass.getpass("Cloudflare Access Client Secret (hidden): ") if access_id else ""
        if access_id:
            if (not 8 <= len(access_id) <= 255 or not 8 <= len(access_secret) <= 4096 or
                    any(ord(c) < 33 or ord(c) > 126 for c in access_id + access_secret)):
                raise ValueError("invalid Cloudflare Access service credentials")
        return json.dumps({"url": url, "token": token,
                           "access_id": access_id, "access_secret": access_secret})

    def bot_gateway_config(self):
        payload = self.gateway_auth_inputs()
        # Do not store the settings (or release queued events) until the
        # actual Gserver container verifies private HTTPS + Gateway auth.
        self.bot_gateway_preflight(payload)
        script = (
            "import json,os,secrets,sys\n"
            "values=json.load(sys.stdin)\n"
            "for label,name in [('access_id','gateway-access-client-id'),"
            "('access_secret','gateway-access-client-secret'),"
            "('token','gateway-token'),('url','gateway-url')]:\n"
            " p='/var/lib/gserver/'+name\n"
            " if os.path.islink(p): raise RuntimeError('SYMLINK_REFUSED')\n"
            " temp=p+'.tmp-'+secrets.token_hex(8)\n"
            " fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n"
            " try:\n"
            "  os.write(fd,values[label].encode('ascii'))\n"
            "  os.fsync(fd)\n"
            " finally:\n"
            "  os.close(fd)\n"
            " os.replace(temp,p)\n"
            " os.chmod(p,0o600)\n"
            "print('GATEWAY_PRIVATE_CONFIG=SET')\n"
        )
        result = subprocess.run(
            self.docker + ["exec", "-i", "gace-gserver-gserver-1", "python3", "-c", script],
            input=payload, capture_output=True, text=True, timeout=30, check=True)
        print(result.stdout.rstrip())

    def bot_gateway_canary(self):
        """One Gateway canary; never store settings or claim the live Bot spool."""
        payload = self.gateway_auth_inputs()
        self.bot_gateway_preflight(payload)
        probe = (
            "import json,sys,uuid\n"
            "from datetime import datetime,timezone\n"
            "sys.path.insert(0,'/opt/gserver/app')\n"
            "from tgs_bridge import envelope,validate,send_gateway\n"
            "value=json.load(sys.stdin)\n"
            "headers={}\n"
            "if value.get('access_id'):\n"
            " headers['CF-Access-Client-Id']=value['access_id']\n"
            " headers['CF-Access-Client-Secret']=value['access_secret']\n"
            "event={'bot':'gserver-probe','event_id':'probe-'+uuid.uuid4().hex,\n"
            "       'event':'bot.started','level':'info','outcome':'PASS'}\n"
            "data=envelope(validate(event),occurred_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))\n"
            "print('PRODUCER_EVENT_ID='+data['eventId'],flush=True)\n"
            "outcome=send_gateway(data,value['url'],value['token'],access_headers_override=headers)\n"
            "if outcome!='ack': sys.exit(11)\n"
            "print('GATEWAY_CANARY_202=PASS')\n"
        )
        result = subprocess.run(
            self.docker + ["exec", "-i", "gace-gserver-gserver-1", "python3", "-c", probe],
            input=payload, capture_output=True, text=True, timeout=20)
        output = result.stdout.strip().splitlines()
        # Print only a known public correlation key, never raw subprocess output.
        if not output or not re.fullmatch(
                r"PRODUCER_EVENT_ID=gserver:gserver-probe:probe-[a-f0-9]{32}", output[0]):
            raise ValueError("gateway canary correlation missing")
        print(output[0])
        if result.returncode != 0 or output[-1] != "GATEWAY_CANARY_202=PASS":
            raise ValueError("gateway canary not confirmed")
        print("GATEWAY_CANARY_202=PASS")

    def action(self, action, image=None):
        if action == "recover":
            return self.recover()
        if self.pending.exists():
            raise ValueError("interrupted operation; run recover first")
        if action == "activate":
            return self.activate(image or "")
        if action in ("bot-init", "bot-status", "bot-smoke", "bot-gateway-canary", "bot-gateway-config", "bot-retry"):
            release = self.load()
            if not release.get("current"):
                raise ValueError("Gserver must be activated first")
            if action == "bot-init":
                return self.bot_init()
            if action == "bot-status":
                return self.bot_status()
            if action == "bot-smoke":
                return self.bot_smoke()
            if action == "bot-retry":
                return self.bot_retry()
            if action == "bot-gateway-canary":
                return self.bot_gateway_canary()
            return self.bot_gateway_config()
        release = self.load()
        if action == "rollback":
            if not release.get("previous"):
                raise ValueError("no previous release")
            return self.activate(release["previous"])
        if not release.get("current"):
            raise ValueError("no installed release")
        if action in ("enable-storage", "disable-storage"):
            if release.get("access") != "loopback":
                raise ValueError("enable local access first")
            if action == "enable-storage":
                if release.get("storage"):
                    return self.compose(release["current"], ["ps", "--all"], "loopback", True)
                prepare_storage()
                self.ensure_token()
                return self.activate(release["current"], storage=True)
            if not release.get("storage"):
                return self.compose(release["current"], ["ps", "--all"], "loopback")
            return self.activate(release["current"], storage=False)
        if action == "storage-list":
            if not release.get("storage"):
                raise ValueError("storage is not enabled")
            code = (
                "from pathlib import Path; import json,urllib.request;"
                "t=Path('/var/lib/gserver/auth-token').read_text().strip();"
                "q=urllib.request.Request('http://127.0.0.1:8765/files',"
                "headers={'Authorization':'Bearer '+t});"
                "r=urllib.request.urlopen(q,timeout=10);"
                "print(r.read(65536).decode())"
            )
            result = self.run(["exec", "gace-gserver-gserver-1", "python3", "-c", code], capture=True)
            print(result.stdout.rstrip())
            return
        if action in ("enable-local", "disable-local"):
            desired = "loopback" if action == "enable-local" else "isolated"
            if desired == "isolated" and release.get("storage"):
                raise ValueError("disable storage before local access")
            if desired == release.get("access", "isolated"):
                if desired == "loopback":
                    # Reconcile a recorded loopback profile whose actual port was
                    # silently omitted on an internal-only Docker 29 bridge.
                    return self.activate(release["current"], access=desired)
                return self.compose(release["current"], ["ps", "--all"], desired)
            if desired == "loopback":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind(("127.0.0.1", LOOPBACK_PORT))
            return self.activate(release["current"], access=desired)
        args = {"start": ["up", "-d", "--wait", "--wait-timeout", "60"],
                "stop": ["stop", "--timeout", "10"],
                "status": ["ps", "--all"],
                "logs": ["logs", "--tail", "50", "--no-color"]}[action]
        self.compose(release["current"], args, release.get("access", "isolated"), release.get("storage", False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["activate", "start", "stop", "status", "logs", "rollback", "recover", "enable-local", "disable-local", "enable-storage", "disable-storage", "storage-list", "bot-init", "bot-status", "bot-smoke", "bot-gateway-canary", "bot-gateway-config", "bot-retry"])
    parser.add_argument("image", nargs="?")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(STATE / "operation.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Controller().action(args.action, args.image)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("GSERVER_OPERATION_FAILED: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
