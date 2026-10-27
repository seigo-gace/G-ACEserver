#!/usr/bin/env python3
"""Offline lifecycle for the dedicated Gserver Compose project; never deletes data."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "gserver"
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")


class Controller:
    def __init__(self, state=STATE):
        self.state = state
        self.record = state / "releases.json"
        self.pending = state / "pending.json"
        self.docker = ["docker"] if os.geteuid() == 0 else ["sudo", "-n", "docker"]

    def run(self, args, capture=False, env=None):
        return subprocess.run(self.docker + args, check=True, text=True,
                              capture_output=capture, timeout=180, env=env)

    def load(self):
        if not self.record.exists():
            return {}
        data = json.loads(self.record.read_text())
        if any(k not in ("current", "previous") or not IMAGE.fullmatch(v)
               for k, v in data.items()):
            raise ValueError("invalid release record")
        return data

    def write_atomic(self, target, data):
        temporary = target.with_suffix(".tmp")
        with open(temporary, "w") as stream:
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        directory = os.open(self.state, os.O_RDONLY | os.O_DIRECTORY)
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
        target = pending.get("target", "")
        if not IMAGE.fullmatch(target):
            raise ValueError("invalid pending image")
        release = self.load()
        if release.get("current"):
            self.compose(release["current"], ["up", "-d", "--wait", "--wait-timeout", "60"])
        else:
            self.compose(target, ["stop", "--timeout", "10"])
        self.pending.unlink()

    def compose(self, image, args):
        if not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        env = dict(os.environ, GSERVER_IMAGE=image)
        return self.run(["compose", "--project-name", "gace-gserver", "-f",
                         str(ROOT / "deploy/compose.gserver.yaml"), *args], env=env)

    def activate(self, image):
        if self.pending.exists():
            raise ValueError("interrupted operation; run recover first")
        if not IMAGE.fullmatch(image):
            raise ValueError("immutable sha256 image ID required")
        old = self.load()
        self.run(["image", "inspect", image], capture=True)
        # First installation may not take over an existing project.
        if not old:
            existing = self.run(["ps", "-aq", "--filter",
                                 "label=com.docker.compose.project=gace-gserver"], capture=True)
            volumes = self.run(["volume", "ls", "-q", "--filter",
                                "label=com.docker.compose.project=gace-gserver"], capture=True)
            if existing.stdout.strip() or volumes.stdout.strip():
                raise ValueError("unowned Gserver project exists; inspect before adoption")
        self.write_atomic(self.pending, {"target": image})
        try:
            self.compose(image, ["up", "-d", "--wait", "--wait-timeout", "60"])
        except (subprocess.SubprocessError, OSError):
            if old.get("current"):
                self.compose(old["current"], ["up", "-d", "--wait", "--wait-timeout", "60"])
            else:
                self.compose(image, ["stop", "--timeout", "10"])
            self.pending.unlink()
            raise
        new = {"current": image}
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
        args = {"start": ["up", "-d", "--wait", "--wait-timeout", "60"],
                "stop": ["stop", "--timeout", "10"],
                "status": ["ps", "--all"],
                "logs": ["logs", "--tail", "50", "--no-color"]}[action]
        self.compose(release["current"], args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["activate", "start", "stop", "status", "logs", "rollback", "recover"])
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
