"""Owner-only local registration for admitted CHAT read-only Git observation."""
import json
import os
from pathlib import Path
import stat

SCHEMA = "gserver.chat-host-registration.v1"
LIMIT = 8192


class RegistrationError(ValueError):
    pass


def default_path():
    return Path.home() / ".local/state/gserver/chat-host-registration.json"


def load(path=None):
    path = Path(path or default_path()).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise RegistrationError("REGISTRATION_MISSING")
    if path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077:
        raise RegistrationError("REGISTRATION_PERMISSIONS")
    raw = path.read_bytes()
    if not 0 < len(raw) <= LIMIT:
        raise RegistrationError("REGISTRATION_SIZE")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegistrationError("REGISTRATION_INVALID") from exc
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA
            or data.get("project") != "Gserver"
            or data.get("repository") != "seigo-gace/G-ACEserver"
            or not isinstance(data.get("change_unit"), str)
            or not isinstance(data.get("registered_checkout"), str)):
        raise RegistrationError("REGISTRATION_SHAPE")
    checkout = Path(data["registered_checkout"]).expanduser().absolute()
    if checkout.is_symlink() or not checkout.is_dir():
        raise RegistrationError("CHECKOUT_INVALID")
    return {
        "change_unit": data["change_unit"],
        "registered_checkout": checkout,
        "repository": data["repository"],
    }


def install(checkout, change_unit="GSR-CHAT-HOST-01", path=None):
    path = Path(path or default_path()).expanduser().absolute()
    checkout = Path(checkout).expanduser().absolute()
    if checkout.is_symlink() or not checkout.is_dir():
        raise RegistrationError("CHECKOUT_INVALID")
    directory = path.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.geteuid():
        raise RegistrationError("STATE_DIR_PERMISSIONS")
    payload = {
        "schema": SCHEMA,
        "project": "Gserver",
        "repository": "seigo-gace/G-ACEserver",
        "change_unit": change_unit,
        "registered_checkout": str(checkout),
    }
    encoded = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    install_p = sub.add_parser("install", help="Write owner-only registration for this checkout")
    install_p.add_argument("checkout", help="Absolute G-ACEserver working tree")
    install_p.add_argument("--change-unit", default="GSR-CHAT-HOST-01")
    install_p.add_argument("--path", help="Registration file (default: ~/.local/state/gserver/...)")
    args = parser.parse_args()
    if args.action == "install":
        path = install(args.checkout, change_unit=args.change_unit, path=args.path)
        print("CHAT_HOST_REGISTRATION=" + str(path))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
