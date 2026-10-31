"""Offline contract integration: admission -> durable claim -> registered Git observation.

This is deliberately **not** a network receiver. Host credentials and the
authenticated external ingress must be supplied only by an independently
approved host adapter after local PC verification.
"""
from datetime import datetime
from pathlib import Path
from chat_host_admission import validate_read_only_request
from chat_host_checkout import observe_owned_checkout
from chat_host_ledger import RequestLedger, ReplayDenied, canonical_fingerprint

def inspect_once(request: dict, *, change_unit: str, source_sha: str,
                 now: datetime, registered_checkout: Path, ledger: RequestLedger) -> dict:
    validated = validate_read_only_request(request, expected_cu=change_unit,
                                            expected_sha=source_sha, now=now)
    if not ledger.claim(validated["request_id"], canonical_fingerprint(request)):
        raise ReplayDenied("DUPLICATE_REQUEST")
    # Consume request ID before checkout observation: failed/unknown outcomes
    # may never be automatically rerun with the same request ID.
    try:
        result = observe_owned_checkout(registered_checkout,
                                        registered_root=registered_checkout,
                                        expected_sha=source_sha,
                                        command_id=validated["command_id"])
    except Exception:
        raise  # Fail closed: the claimed request remains consumed.
    return {"request_id": validated["request_id"], "result": result}
