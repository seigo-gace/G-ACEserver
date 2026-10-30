#!/usr/bin/env bash
# Existing terminal authentication only. No install/restart/repair/secret output.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest discover -s tests -p 'test_gserver_apps*.py' -q >/dev/null
python3 -B -m unittest discover -s tests -p test_gserver_recovery_check.py -q >/dev/null
sudo -v
python3 -B scripts/gserver_recovery_check.py
python3 -B scripts/smoke_gserver_apps_host.py
