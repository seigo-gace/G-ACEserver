#!/usr/bin/env bash
# One-block JP VPN live acceptance on Master WSL (sudo required). No Core restart.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest tests.test_gserver_vpn tests.test_smoke_gserver_vpn_live_contract tests.test_gserver_vpn_guard_smoke -q
sudo -v
python3 -B scripts/gserver_connection_readiness.py --local-status
python3 -B scripts/smoke_gserver_vpn_live.py
