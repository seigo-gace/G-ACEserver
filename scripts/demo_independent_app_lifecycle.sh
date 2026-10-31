#!/usr/bin/env bash
# Single disposable app: verify, start, restart, config update, rollback compose, stop.
# Reuses the running Core immutable image; does not redeploy Core or touch other projects.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -B -m unittest discover -s tests -p 'test_gserver_apps*.py' -q
sudo -v
exec python3 -B scripts/demo_independent_app_lifecycle.py
