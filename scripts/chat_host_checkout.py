"""Local fixed Git read-only commands for an independently authenticated PC caller.

Not a receiver: no network or credential handling, no shell, no arbitrary argv.
Only use after validate_read_only_request and replay/admission checks.
"""
from pathlib import Path
import subprocess
from chat_host_admission import AdmissionDenied

def observe_owned_checkout(checkout: Path, *, expected_sha: str, command_id: str) -> dict:
    """Return bounded metadata, never names, stdout, secrets or private paths."""
    if command_id not in ("project.git_head", "project.git_status"):
        raise AdmissionDenied("COMMAND_NOT_ADMITTED")
    if not isinstance(expected_sha, str) or len(expected_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise AdmissionDenied("EXPECTED_SHA_INVALID")
    if not isinstance(checkout, Path) or checkout.is_symlink() or not checkout.is_dir():
        raise AdmissionDenied("CHECKOUT_INVALID")
    root = checkout.resolve(strict=True)
    def git(*args):
        try:
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", *args],
                cwd=root, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=5, check=False,
                env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
                     "GIT_CONFIG_GLOBAL": "/dev/null"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdmissionDenied("LOCAL_GIT_UNAVAILABLE") from exc
        if result.returncode or len(result.stdout) > 65536:
            raise AdmissionDenied("LOCAL_GIT_FAILED")
        return result.stdout.strip()
    actual_root = Path(git("rev-parse", "--show-toplevel")).resolve(strict=True)
    if actual_root != root:
        raise AdmissionDenied("CHECKOUT_ROOT_MISMATCH")
    head = git("rev-parse", "HEAD")
    if head != expected_sha:
        raise AdmissionDenied("SOURCE_SHA_MISMATCH")
    if command_id == "project.git_head":
        return {"source_sha": head, "head_matches": True}
    dirty = bool(git("status", "--porcelain", "--untracked-files=all"))
    return {"source_sha": head, "worktree_clean": not dirty}
