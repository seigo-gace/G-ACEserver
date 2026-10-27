#!/usr/bin/env bash
# Read-only, non-published Gserver staging smoke; no source modifications.
(
  set -Eeuo pipefail
  phase=PRECHECK
  project=gace-gserver-source-smoke
  compose_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/compose.gserver.staging.yaml"
  started=0
  finish() {
    local result=$?
    trap - EXIT
    if (( started == 1 )); then
      phase=TEARDOWN
      if ! sudo timeout 35 docker compose -p "$project" -f "$compose_file" down --timeout 10 >/dev/null; then
        echo 'ERROR=STAGING_TEARDOWN_FAILED'
        result=33
      fi
    fi
    if (( result == 0 )); then
      echo 'VERIFY=PASS;STAGING_HTTP=200;HOST_PORTS=NONE;SOURCE_MUTATIONS=NONE'
    else
      echo "VERIFY=FAIL;PHASE=$phase;EXIT_CODE=$result"
    fi
    printf '%s\n' 'PROJECT_END=Gserver' '========== GACE_RESULT_END =========='
  }
  trap finish EXIT
  printf '%s\n' '========== GACE_RESULT_BEGIN ==========' 'PROJECT=Gserver' 'ACTION=STAGING_GSERVER_CONTAINER_SMOKE' 'ENV=WSL_UBUNTU'
  cd /mnt/g/Project/Gserver || { echo 'ERROR=GSERVER_ROOT_MISSING'; exit 10; }
  export GSERVER_SOURCE_FILE=/mnt/g/Project/Gserver/app/gserver.py
  [[ -f "$GSERVER_SOURCE_FILE" && ! -L "$GSERVER_SOURCE_FILE" ]] || { echo 'ERROR=SOURCE_FILE_MISSING'; exit 11; }
  sha="$(sha256sum "$GSERVER_SOURCE_FILE" | cut -d' ' -f1)"
  [[ "$sha" == 41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c ]] || { echo 'ERROR=SOURCE_SHA_CHANGED'; exit 12; }
  [[ -f "$compose_file" ]] || { echo 'ERROR=COMPOSE_FILE_MISSING'; exit 13; }
  grep -Eqi '(microsoft|wsl)' /proc/sys/kernel/osrelease || { echo 'ERROR=NOT_WSL'; exit 14; }
  command -v sudo >/dev/null && command -v docker >/dev/null || { echo 'ERROR=DOCKER_NOT_AVAILABLE'; exit 15; }
  phase=SUDO
  sudo -v || { echo 'ERROR=SUDO_ACCESS_FAILED'; exit 16; }
  phase=COMPOSE_VALIDATE
  sudo timeout 25 docker compose -p "$project" -f "$compose_file" config --quiet || { echo 'ERROR=COMPOSE_INVALID'; exit 17; }
  phase=EXISTING_PROJECT_GUARD
  existing="$(sudo timeout 15 docker ps -aq --filter "label=com.docker.compose.project=$project")"
  [[ -z "$existing" ]] || { echo 'ERROR=STAGING_PROJECT_ALREADY_EXISTS'; exit 18; }
  before_podman="$(systemctl is-active podman.socket || true)"
  before_redis="$(systemctl is-active redis-server.service || true)"
  before_site="$(systemctl is-active site_total.service || true)"
  phase=PULL_PYTHON_IMAGE
  sudo timeout 240 docker compose -p "$project" -f "$compose_file" pull --quiet || { echo 'ERROR=STAGING_IMAGE_PULL_FAILED'; exit 19; }
  phase=START_ISOLATED_CONTAINER
  started=1
  sudo timeout 100 docker compose -p "$project" -f "$compose_file" up -d --wait --wait-timeout 50 || { echo 'ERROR=STAGING_HEALTH_FAILED'; exit 20; }
  phase=VERIFY_HEALTH
  id="$(sudo timeout 12 docker compose -p "$project" -f "$compose_file" ps -q gserver-staging)"
  [[ -n "$id" ]] || { echo 'ERROR=STAGING_CONTAINER_MISSING'; exit 21; }
  host_ports="$(sudo timeout 15 docker port "$id")"
  [[ -z "$host_ports" ]] || { echo 'ERROR=STAGING_HOST_PORT_EXPOSED'; exit 22; }
  sudo timeout 15 docker exec "$id" python3 -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=3); assert r.status==200; r.close()" || { echo 'ERROR=STAGING_HTTP_FAILED'; exit 23; }
  phase=REGRESSION_CHECK
  [[ "$(systemctl is-active podman.socket || true)" == "$before_podman" && "$(systemctl is-active redis-server.service || true)" == "$before_redis" && "$(systemctl is-active site_total.service || true)" == "$before_site" ]] || { echo 'ERROR=EXISTING_SERVICE_CHANGED'; exit 24; }
  echo 'STAGING_HTTP=200;EXTERNAL_NETWORK=NONE;PUBLISHED_PORTS=NONE'
)
