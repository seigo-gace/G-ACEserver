"""Pure non-executing admission for a future local Gserver CHAT receiver.

Transport authentication, durable replay protection, local Git verification and
execution must be independently implemented by the actual PC-side owner.
"""
from datetime import datetime, timezone
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"req_[a-z0-9]{12,40}\Z")
CU = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}\Z")
FIELDS = frozenset({"request_id", "project", "change_unit", "repository", "source_sha", "command_id", "effect", "issued_at"})
COMMANDS = frozenset({"project.git_head", "project.git_status"})


class AdmissionDenied(ValueError):
    pass


def validate_read_only_request(request: dict, *, expected_cu: str, expected_sha: str, now: datetime) -> dict:
    """Return bounded metadata, never an executable command."""
    if not isinstance(request, dict) or set(request) != FIELDS:
        raise AdmissionDenied("REQUEST_SHAPE_INVALID")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise AdmissionDenied("EXPECTED_SHA_INVALID")
    if request["project"] != "Gserver" or request["repository"] != "seigo-gace/G-ACEserver":
        raise AdmissionDenied("TARGET_NOT_REGISTERED")
    if not isinstance(request["request_id"], str) or not ID.fullmatch(request["request_id"]):
        raise AdmissionDenied("REQUEST_ID_INVALID")
    if (not isinstance(request["change_unit"], str) or not CU.fullmatch(request["change_unit"])
            or request["change_unit"] != expected_cu):
        raise AdmissionDenied("CHANGE_UNIT_MISMATCH")
    if (not isinstance(request["effect"], str) or request["effect"] != "read_only"\n            or not isinstance(request["command_id"], str) or request["command_id"] not in COMMANDS):
        raise AdmissionDenied("COMMAND_NOT_ADMITTED")
    if (not isinstance(request["source_sha"], str) or not SHA.fullmatch(request["source_sha"])
            or request["source_sha"] != expected_sha):
        raise AdmissionDenied("SOURCE_SHA_MISMATCH")
    if not isinstance(request["issued_at"], str) or not isinstance(now, datetime) or now.tzinfo is None:
        raise AdmissionDenied("TIME_INVALID")
    try:
        issued = datetime.fromisoformat(request["issued_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdmissionDenied("TIME_INVALID") from exc
    if issued.tzinfo is None:
        raise AdmissionDenied("TIME_INVALID")
    seconds = (now.astimezone(timezone.utc) - issued.astimezone(timezone.utc)).total_seconds()
    if not 0 <= seconds <= 60:
        raise AdmissionDenied("REQUEST_EXPIRED_OR_FUTURE")
    return {"request_id": request["request_id"], "command_id": request["command_id"], "source_sha": expected_sha}
