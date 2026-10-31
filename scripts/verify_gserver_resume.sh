#!/usr/bin/env bash
# Existing terminal authentication only. No install/restart/repair/secret output.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest discover -s tests -p 'test_gserver_apps*.py' -q >/dev/null
python3 -B -m unittest discover -s tests -p test_gserver_recovery_check.py -q >/dev/null
sudo -v
python3 -B scripts/gserver_recovery_check.py
python3 -B scripts/smoke_gserver_apps_host.py
python3 -B scripts/smoke_gserver_vpn_guard.py
python3 -B scripts/audit_f01_wsl_boot.py
python3 -B scripts/f03_storage_mount_audit.py
python3 -B scripts/gserver_f04_readiness.py
