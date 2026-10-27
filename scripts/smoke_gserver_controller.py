#!/usr/bin/env python3
"""Exercise the real controller with disposable isolated volumes and two image IDs."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

from gserverctl import Controller, IMAGE, ROOT


def verify(image):
    if not IMAGE.fullmatch(image):
        raise ValueError("immutable image required")
    with tempfile.TemporaryDirectory(prefix="gserver-controller-") as directory:
        state = Path(directory)
        project = "gace-gserver-test-" + uuid.uuid4().hex[:16]
        controller = Controller(state, project=project)
        image_file = state / "fixture-image"
        print('CONTROLLER_PHASE=BUILD_FIXTURE', flush=True)
        # Same application, different label: tests version selection, not schema migration.
        controller.run(["build", "--network=none", "--label",
                        "org.gace.verification.variant=rollback-fixture", "--iidfile", str(image_file),
                        "-f", str(ROOT / "Dockerfile"), str(ROOT)], capture=True)
        previous = image_file.read_text().strip()
        if not IMAGE.fullmatch(previous) or previous == image:
            raise ValueError("distinct rollback fixture required")
        owned = False
        try:
            # A random test project must still be empty before any cleanup is authorized.
            for command in (["ps", "-aq"], ["volume", "ls", "-q"]):
                result = controller.run(command + ["--filter", "label=com.docker.compose.project=" + project], capture=True)
                if result.stdout.strip():
                    raise ValueError("test project already exists")
            owned = True
            print('CONTROLLER_PHASE=INITIAL_ACTIVATION', flush=True)
            controller.activate(previous)

            def container(expected):
                result = controller.run(["ps", "-q", "--filter", "label=com.docker.compose.project=" + project], capture=True)
                ids = result.stdout.split()
                if len(ids) != 1:
                    raise ValueError("expected one isolated container")
                cid = ids[0]
                result = controller.run(["inspect", "--format", '{{json .}}', cid], capture=True)
                details = json.loads(result.stdout)
                if details['Image'] != expected or details['HostConfig']['NetworkMode'] != 'none':
                    raise ValueError("image/network mismatch")
                if details['HostConfig'].get('PortBindings'):
                    raise ValueError("unexpected published ports")
                return cid

            cid = container(previous)
            controller.run(["exec", cid, "python3", "-c",
                            "from pathlib import Path; Path('/var/lib/gserver/logs/recovery-proof').write_text('isolated-fixture')"])
            print('CONTROLLER_PHASE=UPDATE', flush=True)
            controller.activate(image)
            container(image)
            print('CONTROLLER_PHASE=ROLLBACK', flush=True)
            controller.action("rollback")
            container(previous)
            print('CONTROLLER_PHASE=STOP_START', flush=True)
            controller.action("stop")
            controller.action("start")
            cid = container(previous)
            controller.run(["exec", cid, "python3", "-c",
                            "from pathlib import Path; assert Path('/var/lib/gserver/logs/recovery-proof').read_text()=='isolated-fixture'"])
        finally:
            if owned:
                print('CONTROLLER_PHASE=CLEANUP', flush=True)
                # Only the random project created above; production controller never uses -v.
                controller.compose(previous, ["down", "--volumes", "--timeout", "10"])
        print("CONTROLLER_SMOKE=PASS;IMAGE_UPDATE_ROLLBACK=PASS;PERSISTENCE=PASS;HOST_PORTS=NONE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    try:
        verify(parser.parse_args().image)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("CONTROLLER_SMOKE=FAIL;ERROR=" + type(error).__name__)
        raise SystemExit(1)
