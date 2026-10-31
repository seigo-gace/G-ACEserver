#!/usr/bin/env bash
# Local PC E2E: unit tests + one read-only Git request + duplicate rejection.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
python3 -B -m unittest discover -s tests -p 'test_chat_host*.py' -q
CHECKOUT="${GSERVER_CHAT_HOST_CHECKOUT:-$HOME/Project/Gserver/repository}"
STATE="$(mktemp -d "${TMPDIR:-/tmp}/gserver-chat-host.XXXXXX")"
chmod 700 "$STATE"
REG="$STATE/chat-host-registration.json"
LEDGER="$STATE/chat-host-verify-claims.sqlite"
export GSERVER_CHAT_HOST_REGISTRATION="$REG"
export GSERVER_CHAT_HOST_LEDGER="$LEDGER"
python3 -B - "$CHECKOUT" "$REG" <<'PY'
import sys
from pathlib import Path
from chat_host_registration import install
install(Path(sys.argv[1]), path=Path(sys.argv[2]))
print("REGISTRATION=PASS")
PY
HEAD="$(git -C "$CHECKOUT" rev-parse HEAD)"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REQ_ID="req_$(openssl rand -hex 8)"
REQUEST="$(python3 -B - "$REQ_ID" "$HEAD" "$NOW" <<'PY'
import json, sys
print(json.dumps({
  "request_id": sys.argv[1],
  "project": "Gserver",
  "change_unit": "GSR-CHAT-HOST-01",
  "repository": "seigo-gace/G-ACEserver",
  "source_sha": sys.argv[2],
  "command_id": "project.git_head",
  "effect": "read_only",
  "issued_at": sys.argv[3],
}))
PY
)"
run_once() {
  python3 -B scripts/chat_host_local_run.py <<EOF
$1
EOF
}
OUT="$(run_once "$REQUEST")"
echo "$OUT"
echo "$OUT" | rg -q 'CHAT_HOST_OK=PASS'
echo "$OUT" | rg -Fq "CHAT_HOST_SOURCE_SHA=${HEAD}"
DUP="$(run_once "$REQUEST" || true)"
echo "$DUP"
echo "$DUP" | rg -q 'CHAT_HOST_OK=FAIL'
echo "$DUP" | rg -Fq 'CHAT_HOST_CODE=DUPLICATE_REQUEST'
EXPIRED_ID="req_$(openssl rand -hex 8)"
EXPIRED="$(python3 -B - "$EXPIRED_ID" "$HEAD" <<'PY'
import json, sys
from datetime import datetime, timezone, timedelta
old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
print(json.dumps({
  "request_id": sys.argv[1],
  "project": "Gserver",
  "change_unit": "GSR-CHAT-HOST-01",
  "repository": "seigo-gace/G-ACEserver",
  "source_sha": sys.argv[2],
  "command_id": "project.git_head",
  "effect": "read_only",
  "issued_at": old,
}))
PY
)"
EXOUT="$(run_once "$EXPIRED" || true)"
echo "$EXOUT" | rg -q 'CHAT_HOST_OK=FAIL'
echo "$EXOUT" | rg -Fq 'CHAT_HOST_CODE=REQUEST_EXPIRED_OR_FUTURE'
rm -rf "$STATE"
echo "CHAT_HOST_LOCAL_E2E=PASS"
