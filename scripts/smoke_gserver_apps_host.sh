#!/usr/bin/env bash
# One foreground acceptance; authentication stays in the owner's terminal.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -B -m unittest discover -s tests -p 'test_gserver_apps*.py' -q
sudo -v
python3 -B scripts/smoke_gserver_apps_host.py
