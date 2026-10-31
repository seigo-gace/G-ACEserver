#!/usr/bin/env bash
# Isolated single-region or sequential JP/KR acceptance; no Core restart.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mode="${1:-}"
if [[ $# -gt 1 || ( -n "$mode" && "$mode" != --both && "$mode" != --cloudflare-local ) ]]; then
    echo 'Usage: verify_vpn_live_host.sh [--both|--cloudflare-local]' >&2
    exit 2
fi
python3 -B -m unittest tests.test_gserver_vpn tests.test_smoke_gserver_vpn_live_contract tests.test_gserver_vpn_guard_smoke tests.test_verify_vpn_live_host tests.test_cloudflared_local_audit -q
sudo -v
if [[ "$mode" == --cloudflare-local ]]; then
    python3 -B scripts/audit_gserver_cloudflared_host.py
    exit $?
fi
python3 -B scripts/gserver_connection_readiness.py --local-status
if [[ "$mode" == --both ]]; then
    GSERVER_VPN_REGION=jp GSERVER_VPN_LEARN_BACKUP=kr python3 -B scripts/smoke_gserver_vpn_live.py
    # set -e requires JP checks, cleanup and private pin commit to succeed first.
    GSERVER_VPN_REGION=kr GSERVER_VPN_LEARN_BACKUP= python3 -B scripts/smoke_gserver_vpn_live.py
else
    python3 -B scripts/smoke_gserver_vpn_live.py
fi
