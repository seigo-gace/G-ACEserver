#!/usr/bin/env python3
"""Bounded, read-only source inventory for the two documented PC Gserver candidates.

Only code metadata and possible GitHub-runtime-dependency categories are saved.
No process, network, Git, credential, configuration, or service changes are made.
"""
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

CANDIDATES = {
    "g_drive_app": Path("/mnt/g/Project/Gserver/app"),
    "wsl_service": Path("/srv/gserver"),
}
DISCOVERY_BASES = {"g_projects": Path("/mnt/g/Project"), "web_apps": Path("/www/dk_project"), "srv": Path("/srv")}
SUFFIXES = {".py", ".ps1", ".sh", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".php", ".html", ".css", ".service"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "data", "logs", "backups", "backup", "spool", "runtime", "dist", "build"}
SKIP_NAMES = ("secret", "credential", "password", "token", "private", "keyfile", "apikey")
MAX_FILES, MAX_BYTES, MAX_HINTS, MAX_DIRS = 1000, 2_000_000, 30, 200
HINTS = {
    "github_api": re.compile(r"api\.github\.com|github\.com/[^\s/]+/[^\s/]+", re.I),
    "github_auth": re.compile(r"GITHUB_TOKEN|GH_TOKEN|GITHUB_OAUTH|GITHUB_API", re.I),
    "git_network": re.compile(r"\bgit\s+(?:clone|fetch|pull)\b", re.I),
    "actions": re.compile(r"github[_-]actions|/actions/(?:workflows|runs)", re.I),
}


def discover_named_roots(bases: dict) -> dict:
    """Only discover named Gserver directories under bounded documented parent roots."""
    found = {}
    for label, base in bases.items():
        if base.is_symlink() or not base.is_dir():
            continue
        seen = 0
        for parent, dirs, _ in os.walk(base, topdown=True, followlinks=False):
            seen += 1
            depth = len(Path(parent).relative_to(base).parts)
            if seen > MAX_DIRS or depth >= 3:
                dirs[:] = []
                continue
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS and not (Path(parent) / d).is_symlink())
            for name in dirs:
                if name.lower() == "gserver" and len(found) < 8:
                    found["discovered_" + label + "_" + str(len(found) + 1)] = Path(parent) / name
    return found


def inventory_root(label: str, root: Path) -> dict:
    if root.is_symlink():
        return {"candidate": label, "status": "SYMLINK_ROOT_SKIPPED", "files": []}
    if not root.is_dir():
        return {"candidate": label, "status": "MISSING_OR_NOT_DIRECTORY", "files": []}
    result = {"candidate": label, "status": "READ_ONLY_SCANNED", "files": [], "skipped": 0, "errors": 0}
    walk_errors = []
    visited_dirs = 0
    for parent, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_errors.append):
        visited_dirs += 1
        if visited_dirs > MAX_DIRS:
            result["status"] = "TRUNCATED_DIRECTORY_LIMIT"
            return result
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS and not (Path(parent) / d).is_symlink())
        for name in sorted(files):
            path = Path(parent) / name
            if name.startswith(".") or any(word in name.lower() for word in SKIP_NAMES) or path.suffix.lower() not in SUFFIXES:
                continue
            if len(result["files"]) >= MAX_FILES:
                result["status"] = "TRUNCATED_FILE_LIMIT"
                return result
            try:
                meta = path.lstat()
                if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_BYTES:
                    result["skipped"] += 1
                    continue
                content = path.read_bytes()
                if len(content) > MAX_BYTES:
                    result["skipped"] += 1
                    continue
                hints = []
                for line_no, line in enumerate(content.decode("utf-8", errors="replace").splitlines(), 1):
                    for category, pattern in HINTS.items():
                        if pattern.search(line) and len(hints) < MAX_HINTS:
                            hints.append({"line": line_no, "category": category})
                result["files"].append({"relative": str(path.relative_to(root)), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "review_hints": hints})
            except (OSError, ValueError):
                result["errors"] += 1
    if walk_errors:
        result["errors"] += len(walk_errors)
        result["status"] = "SCAN_PARTIAL_ERROR"
    return result


def main() -> None:
    report = {"schema": 1, "time_utc": datetime.now(timezone.utc).isoformat(), "source_only": True,
              "runtime_not_verified": True, "roots": [inventory_root(label, path) for label, path in {**CANDIDATES, **discover_named_roots(DISCOVERY_BASES)}.items()]}
    folder = Path.home() / ".local" / "state" / "gserver"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / ("pc-source-inventory-" + stamp + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print("LOCAL_REPORT=" + str(path))
    for item in report["roots"]:
        print(item["candidate"] + "=" + item["status"] + ";FILES=" + str(len(item["files"])))
    print("PC_RUNTIME=NOT_VERIFIED; NO_NETWORK_OR_SERVICE_CHANGES=YES")


if __name__ == "__main__":
    main()
