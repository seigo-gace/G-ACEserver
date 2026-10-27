#!/usr/bin/env bash
# Bounded isolated image/persistence test. Only its dedicated test volume is removed.
(
  set -Eeuo pipefail
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  project=gace-gserver-runtime-smoke
  compose_file="$PWD/deploy/compose.gserver.yaml"
  started=0
  image_id_dir="$(mktemp -d)"
  image_id_file="$image_id_dir/image"
  phase=PRECHECK
  finish() {
    result=$?
    trap - EXIT
    if (( started )); then
      if (( result != 0 )); then
        sudo -n env GSERVER_IMAGE="$GSERVER_IMAGE" timeout 15 docker compose -p "$project" -f "$compose_file" logs --no-color --tail 30 || true
      fi
      if ! sudo -n env GSERVER_IMAGE="$GSERVER_IMAGE" timeout 35 docker compose -p "$project" -f "$compose_file" down --volumes --timeout 10; then
        result=33
        phase=CLEANUP
      fi
    fi
    rm -f -- "$image_id_file"
    rmdir -- "$image_id_dir"
    if (( result == 0 )); then
      echo 'VERIFY=PASS;RUNTIME_SMOKE=IMAGE_RECREATE_PERSISTENCE_OFFLINE;PRODUCTION_ACCEPTANCE=NOT_VERIFIED'
    else
      echo "VERIFY=FAIL;PHASE=$phase;EXIT_CODE=$result"
    fi
    echo 'PROJECT_END=Gserver'
    echo '========== GACE_RESULT_END =========='
    exit "$result"
  }
  trap finish EXIT
  echo '========== GACE_RESULT_BEGIN =========='
  echo 'PROJECT=Gserver'
  echo 'ACTION=ISOLATED_PACKAGED_RUNTIME_SMOKE'
  sudo -v
  phase=OWNERSHIP_GUARD
  [[ -z "$(sudo -n timeout 15 docker ps -aq --filter "label=com.docker.compose.project=$project")" ]]
  [[ -z "$(sudo -n timeout 15 docker volume ls -q --filter "label=com.docker.compose.project=$project")" ]]
  before="$(systemctl is-active podman.socket redis-server site_total btpanel || true)"
  phase=BUILD
  sudo -n timeout 300 docker build --network=none --iidfile "$image_id_file" -f Dockerfile .
  GSERVER_IMAGE="$(cat "$image_id_file")"
  [[ "$GSERVER_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]]
  compose() { sudo -n env GSERVER_IMAGE="$GSERVER_IMAGE" timeout 100 docker compose -p "$project" -f "$compose_file" "$@"; }
  phase=START
  started=1
  compose up -d --wait --wait-timeout 60
  id="$(compose ps -q gserver)"
  [[ -n "$id" && -z "$(sudo -n timeout 15 docker port "$id")" ]]
  phase=VERIFY_PERSISTENT_LOG
  sudo -n timeout 15 docker exec "$id" python3 -c 'from pathlib import Path; p=Path("/var/lib/gserver/logs/gserver.log"); assert p.is_file(); p.open("a").write("isolated-persistence-proof\n")'
  phase=RECREATE
  compose up -d --force-recreate --wait --wait-timeout 60
  new_id="$(compose ps -q gserver)"
  [[ -n "$new_id" && "$new_id" != "$id" ]]
  sudo -n timeout 15 docker exec "$new_id" python3 -c 'from pathlib import Path; assert "isolated-persistence-proof" in Path("/var/lib/gserver/logs/gserver.log").read_text()'
  [[ "$(sudo -n timeout 15 docker inspect --format '{{.HostConfig.NetworkMode}}' "$new_id")" == none ]]
  [[ -z "$(sudo -n timeout 15 docker port "$new_id")" ]]
  phase=STOP_START
  compose stop --timeout 10
  compose up -d --wait --wait-timeout 60
  phase=CONTROLLER_UPDATE_ROLLBACK
  python3 scripts/smoke_gserver_controller.py "$GSERVER_IMAGE"
  phase=EXISTING_SERVICES
  [[ "$before" == "$(systemctl is-active podman.socket redis-server site_total btpanel || true)" ]]
)
