#!/usr/bin/env python3
"""Thin Receiver boundary for the shared server-core host.command event.

The Gateway/transport owner must verify delivery authentication before calling
``handle_event``. This module only validates the already-authenticated event
envelope and delegates one target-bound request to the existing Gserver
adapter. It is not a listener, dispatcher, command menu, credential store or
daemon.
"""
from pathlib import Path

from gserver_host_adapter import HostAdapterError, execute_request


DESTINATION = "gserver-bounded-host"
EVENT_TYPE = "gace.servercore-bounded-host.requested"
REPOSITORY = "seigo-gace/G-ACEserver"
TARGET = "gserver"


class ReceiverError(ValueError):
    pass


def handle_event(event, root):
    """Handle one authenticated common-route event and return bounded result."""
    if not isinstance(event, dict):
        raise ReceiverError("GSERVER_EVENT_INVALID")
    required = {"eventId", "eventType", "sourceId", "destinationId", "subject", "time", "data"}
    if set(event) != required:
        raise ReceiverError("GSERVER_EVENT_KEYS_INVALID")
    if event["eventType"] != EVENT_TYPE or event["destinationId"] != DESTINATION:
        raise ReceiverError("GSERVER_EVENT_ROUTE_MISMATCH")
    if event["sourceId"] != "server-core-github":
        raise ReceiverError("GSERVER_EVENT_SOURCE_MISMATCH")
    if event["subject"] != "servercore-bounded-host/host.command":
        raise ReceiverError("GSERVER_EVENT_SUBJECT_INVALID")
    request = event["data"]
    if not isinstance(request, dict) or request.get("id") != event["eventId"]:
        raise ReceiverError("GSERVER_EVENT_REQUEST_MISMATCH")
    if request.get("host_target") != TARGET or request.get("repository") != REPOSITORY:
        raise ReceiverError("GSERVER_EVENT_TARGET_MISMATCH")
    try:
        return execute_request(request, Path(root))
    except HostAdapterError as exc:
        raise ReceiverError(str(exc)) from exc
