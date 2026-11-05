"""Regress direct group authority, sudo fallback and local daemon pinning."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import local_docker
import gserver_apps
from gserverctl import Controller
import audit_f01_wsl_boot


class LocalDockerTests(unittest.TestCase):
    def test_root_and_socket_members_use_direct_docker(self):
        for uid, access in ((0, False), (1000, True)):
            with self.subTest(uid=uid), patch.object(local_docker.os, "geteuid", return_value=uid), patch.object(local_docker.os, "access", return_value=access):
                self.assertEqual(local_docker.docker_command(), ["docker", "--host", local_docker.DOCKER_SOCKET])

    def test_no_socket_authority_keeps_noninteractive_sudo(self):
        with patch.object(local_docker.os, "geteuid", return_value=1000), patch.object(local_docker.os, "access", return_value=False) as access:
            self.assertEqual(local_docker.docker_command(), ["sudo", "-n", "docker", "--host", local_docker.DOCKER_SOCKET])
            access.assert_called_once_with("/var/run/docker.sock", os.R_OK | os.W_OK)

    def test_controller_apps_and_audit_share_authority_and_ignore_remote_context(self):
        with patch.object(local_docker.os, "geteuid", return_value=1000), patch.object(local_docker.os, "access", return_value=True), patch.dict(os.environ, {"DOCKER_HOST": "tcp://untrusted.invalid:2375", "DOCKER_CONTEXT": "remote"}):
            expected = ["docker", "--host", local_docker.DOCKER_SOCKET]
            self.assertEqual(Controller().docker, expected)
            self.assertEqual(gserver_apps.command(Path("/tmp/app/compose.yaml"), "demo")[:3], expected)
            self.assertEqual(audit_f01_wsl_boot.docker_cmd(), expected)
