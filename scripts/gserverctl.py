#!/usr/bin/env python3
"""Offline lifecycle for the dedicated Gserver Compose project; never deletes data."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "gserver"
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
LOOPBACK_PORT = 18765


class Controller:
    def __init__(self, state=STATE, project="gace-gserver"):
        if project != "gace-gserver" and not re.fullmatch(r"gace-gserver-test-[a-f0-9]{16}", project):
            raise ValueError("invalid project")
        self.project = project
        self.state = state
        self.record = state / "releases.json"
        self.pending = state / "pending.json"
        self.docker = (["docker"] if os.geteuid() == 0 else ["sudo", "-n", "docker"]) + ["--host", "unix:///var/run/docker.sock"]

    def bundle(self, image, create=False, access="isolated"):
        if not isinstance(image, str) or not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        if access not in ("isolated", "loopback"):
            raise ValueError("invalid access profile")
        directory = self.state / "bundles"
        manifest = directory / (image[7:] + (".loopback.json" if access == "loopback" else ".json"))
        if create and not manifest.exists():
            source = (ROOT / "deploy/compose.gserver.yaml").read_text()
            source = source.replace("${GSERVER_IMAGE:?immutable_image_required}", image)
            if access == "loopback":
                marker = "    network_mode: none\n"
                if source.count(marker) != 1:
                    raise ValueError("unexpected base network contract")
                source = source.replace(marker,
                    '    ports:\n      - "127.0.0.1:18765:8765"\n'
                    '    networks:\n      - gserver-local\n', 1)
                source += "\nnetworks:\n  gserver-local:\n    internal: true\n"
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
            (k == "access" and v != "loopback") or k not in ("current", "previous", "access")
            for k, v in data.items()
        ):
            raise ValueError("invalid release record")
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
            self.compose(release["current"], ["up", "-d", "--wait", "--wait-timeout", "60"], release.get("access", "isolated"))
        else:
            self.compose(target, ["stop", "--timeout", "10"])
        self.pending.unlink()

    def compose(self, image, args, access="isolated"):
        snapshot = self.bundle(image, access=access)
        # Image is literal in the snapshot: sudo environment filtering is irrelevant.
        return self.run(["compose", "--project-name", self.project, "--env-file", "/dev/null",
                         "--project-directory", str(self.state), "-f", str(snapshot), *args])

    def activate(self, image, access=None):
        if self.pending.exists():
            raise ValueError("interrupted operation; run recover first")
        if not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        old = self.load()
        access = access or old.get("access", "isolated")
        if access not in ("isolated", "loopback"):
            raise ValueError("invalid access profile")
        self.run(["image", "inspect", image], capture=True)
        self.bundle(image, create=True, access=access)
        if old.get("current"):
            self.bundle(old["current"], access=old.get("access", "isolated"))
        # First installation may not take over an existing project.
        if not old:
            existing = self.run(["ps", "-aq", "--filter",
                                 "label=com.docker.compose.project=" + self.project], capture=True)
            volumes = self.run(["volume", "ls", "-q", "--filter",
                                "label=com.docker.compose.project=" + self.project], capture=True)
            if existing.stdout.strip() or volumes.stdout.strip():
                raise ValueError("unowned Gserver project exists; inspect before adoption")
        self.write_atomic(self.pending, {"target": image, "access": access})
        try:
            self.compose(image, ["up", "-d", "--wait", "--wait-timeout", "60"], access)
        except (subprocess.SubprocessError, OSError):
            if old.get("current"):
                self.compose(old["current"], ["up", "-d", "--wait", "--wait-timeout", "60"], old.get("access", "isolated"))
            else:
                self.compose(image, ["stop", "--timeout", "10"])
            self.pending.unlink()
            raise
        new = {"current": image}
        if access == "loopback":
            new["access"] = "loopback"
        if old.get("current") and old["current"] != image:
            new["previous"] = old["current"]
        elif old.get("previous"):
            new["previous"] = old["previous"]
        self.save(new)
        self.pending.unlink()

    def action(self, action, image=None):
        if action == "recover":
            return self.recover()
        if self.pending.exists():
            raise ValueError("interrupted operation; run recover first")
        if action == "activate":
            return self.activate(image or "")
        release = self.load()
        if action == "rollback":
            if not release.get("previous"):
                raise ValueError("no previous release")
            return self.activate(release["previous"])
        if not release.get("current"):
            raise ValueError("no installed release")
        if action in ("enable-local", "disable-local"):
            desired = "loopback" if action == "enable-local" else "isolated"
            if desired == release.get("access", "isolated"):
                return self.compose(release["current"], ["ps", "--all"], desired)
            if desired == "loopback":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind(("127.0.0.1", LOOPBACK_PORT))
            return self.activate(release["current"], access=desired)
        args = {"start": ["up", "-d", "--wait", "--wait-timeout", "60"],
                "stop": ["stop", "--timeout", "10"],
                "status": ["ps", "--all"],
                "logs": ["logs", "--tail", "50", "--no-color"]}[action]
        self.compose(release["current"], args, release.get("access", "isolated"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["activate", "start", "stop", "status", "logs", "rollback", "recover", "enable-local", "disable-local"])
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
