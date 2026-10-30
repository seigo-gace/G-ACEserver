#!/usr/bin/env bash
# Temporary, no-public-port E2E of the generic app manager on the PC.
(
  set -Eeuo pipefail
  cd "$(dirname "$0")/.."
  phase=PRECHECK
  created=0
  dir=''
  name=''
  base_id=''
  cleanup() {
    rc=$?
    trap - EXIT
    if (( created )); then
      if ! sudo -n docker --host unix:///var/run/docker.sock compose \
        --project-name "gace-app-$name" --project-directory "$dir" \
        --env-file /dev/null -f "$dir/compose.yaml" \
        down --remove-orphans --timeout 10 >/dev/null 2>&1; then
        rc=1
        phase=CLEANUP
      fi
    fi
    if [[ -n "$dir" && -d "$dir" ]]; then
      rm -f -- "$dir/compose.yaml"
      rmdir -- "$dir" || rc=1
    fi
    if (( rc == 0 )); then
      echo 'VERIFY=PASS'
      echo 'EXIT_CODE=0'
      echo 'ERROR=NONE'
    else
      echo 'VERIFY=FAIL'
      echo "EXIT_CODE=$rc"
      echo "ERROR=APP_SMOKE_$phase"
    fi
    echo 'PROJECT_END=Gserver'
    echo '========== GACE_RESULT_END =========='
    exit "$rc"
  }
  trap cleanup EXIT
  echo '========== GACE_RESULT_BEGIN =========='
  echo 'PROJECT=Gserver'
  echo 'ACTION=PC_GENERIC_APP_RUNTIME_SMOKE'
  sudo -v
  phase=SOURCE
  test -f scripts/gserver_apps.py
  python3 -B -m unittest discover -s tests -p test_gserver_apps.py -q >/dev/null
  phase=CONTAINER
  base_id="$(sudo -n docker --host unix:///var/run/docker.sock inspect --format '{{.Id}}' gace-gserver-gserver-1)"
  image="$(sudo -n docker --host unix:///var/run/docker.sock inspect --format '{{.Image}}' gace-gserver-gserver-1)"
  [[ "$image" =~ ^sha256:[a-f0-9]{64}$ ]]
  dir="$(mktemp -d /tmp/gserver-app-smoke.XXXXXXXX)"
  name="probe-$(python3 -B -c 'import secrets; print(secrets.token_hex(6))')"
  phase=EXISTING_PROJECT_GUARD
  existing="$(sudo -n docker --host unix:///var/run/docker.sock ps -aq --filter "label=com.docker.compose.project=gace-app-$name")"
  [[ -z "$existing" ]]
  cat >"$dir/compose.yaml" <<EOF
services:
  probe:
    image: $image
    network_mode: none
    restart: 'no'
EOF
  phase=VERIFY_COMPOSE
  python3 -B scripts/gserver_apps.py verify "$name" "$dir/compose.yaml"
  phase=START
  created=1
  python3 -B scripts/gserver_apps.py start "$name" "$dir/compose.yaml"
  phase=STATUS
  status="$(python3 -B scripts/gserver_apps.py status "$name" "$dir/compose.yaml")"
  [[ "$status" == *'APP_SERVICE=probe;STATE=running'* ]]
  echo 'APP_STATUS=RUNNING'
  phase=STOP
  python3 -B scripts/gserver_apps.py stop "$name" "$dir/compose.yaml"
  phase=CORE_UNCHANGED
  after_id="$(sudo -n docker --host unix:///var/run/docker.sock inspect --format '{{.Id}}' gace-gserver-gserver-1)"
  [[ "$base_id" == "$after_id" ]]
  echo 'CORE_CONTAINER_UNCHANGED=PASS'
)
