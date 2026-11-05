"""Select existing local Docker authority; never change groups or permissions."""
import os

DOCKER_SOCKET = "unix:///var/run/docker.sock"
SOCKET_PATH = "/var/run/docker.sock"


def docker_command():
    """Use direct access when available, otherwise existing noninteractive sudo."""
    direct = os.geteuid() == 0 or os.access(SOCKET_PATH, os.R_OK | os.W_OK)
    prefix = ["docker"] if direct else ["sudo", "-n", "docker"]
    return prefix + ["--host", DOCKER_SOCKET]
