#!/usr/bin/env python3
"""Execute one admitted read-only CHAT request on this PC (no network receiver).

Reads JSON from stdin, validates admission + durable claim, runs bounded Git
observation, prints correlated result for the owner terminal / future transport.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from chat_host_admission import AdmissionDenied
from chat_host_ledger import ReplayDenied, RequestLedger
from chat_host_offline import inspect_once
from chat_host_registration import RegistrationError, default_path, load


def emit(payload):
    print("========== GACE_RESULT_BEGIN ==========", flush=True)
    print("PROJECT=Gserver", flush=True)
    print("ACTION=CHAT_HOST_LOCAL_RUN", flush=True)
    print("CHAT_HOST_REQUEST_ID=" + str(payload.get("request_id", "")), flush=True)
    print("CHAT_HOST_SOURCE_SHA=" + str(payload.get("source_sha", "")), flush=True)
    print("CHAT_HOST_COMMAND_ID=" + str(payload.get("command_id", "")), flush=True)
    print("CHAT_HOST_OK=" + ("PASS" if payload.get("ok") else "FAIL"), flush=True)
    if payload.get("code"):
        print("CHAT_HOST_CODE=" + payload["code"], flush=True)
    if payload.get("result") is not None:
        print("CHAT_HOST_RESULT=" + json.dumps(payload["result"], separators=(",", ":"), ensure_ascii=True), flush=True)
    print("VERIFY=" + ("PASS" if payload.get("ok") else "FAIL"), flush=True)
    print("ERROR=" + (payload.get("code") or "NONE"), flush=True)
    print("EXIT_CODE=" + ("0" if payload.get("ok") else "1"), flush=True)
    print("PROJECT_END=Gserver", flush=True)
    print("========== GACE_RESULT_END ==========", flush=True)


def run_request(request, *, registration_path=None, ledger_path=None):
    reg = load(registration_path)
    ledger_file = ledger_path or os.environ.get("GSERVER_CHAT_HOST_LEDGER")
    ledger = RequestLedger(Path(ledger_file or Path.home() / ".local/state/gserver/chat-host-claims.sqlite"))
    now = datetime.now(timezone.utc)
    source_sha = request.get("source_sha", "")
    try:
        body = inspect_once(
            request,
            change_unit=reg["change_unit"],
            source_sha=source_sha,
            now=now,
            registered_checkout=reg["registered_checkout"],
            ledger=ledger,
        )
    except AdmissionDenied as exc:
        return {
            "ok": False,
            "request_id": request.get("request_id"),
            "source_sha": source_sha,
            "command_id": request.get("command_id"),
            "code": str(exc),
        }
    except ReplayDenied as exc:
        return {
            "ok": False,
            "request_id": request.get("request_id"),
            "source_sha": source_sha,
            "command_id": request.get("command_id"),
            "code": str(exc),
        }
    return {
        "ok": True,
        "request_id": body["request_id"],
        "source_sha": source_sha,
        "command_id": request.get("command_id"),
        "code": "NONE",
        "result": body["result"],
    }


def main():
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        emit({"ok": False, "code": "REQUEST_JSON_INVALID", "request_id": "", "source_sha": ""})
        return 1
    if not isinstance(request, dict):
        emit({"ok": False, "code": "REQUEST_JSON_INVALID", "request_id": "", "source_sha": ""})
        return 1
    reg_path = os.environ.get("GSERVER_CHAT_HOST_REGISTRATION")
    ledger_path = os.environ.get("GSERVER_CHAT_HOST_LEDGER")
    try:
        payload = run_request(request, registration_path=reg_path, ledger_path=ledger_path)
    except RegistrationError as exc:
        payload = {
            "ok": False,
            "request_id": request.get("request_id", ""),
            "source_sha": request.get("source_sha", ""),
            "command_id": request.get("command_id"),
            "code": str(exc),
        }
    emit(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
