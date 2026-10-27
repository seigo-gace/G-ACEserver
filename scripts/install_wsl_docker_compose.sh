#!/usr/bin/env bash
# Gserver Ubuntu 24.04 WSL only; never modifies existing apps, data, secrets or Podman.
(
  set -Eeuo pipefail
  phase=PRECHECK
  key_file=''
  finish() {
    local rc=$?
    trap - EXIT
    if [[ -n "$key_file" ]]; then rm -f -- "$key_file"; fi
    if (( rc == 0 )); then
      echo 'VERIFY=PASS;DOCKER_BOOTSTRAP=INSTALLED_AND_SMOKE_VERIFIED'
    else
      echo "VERIFY=FAIL;PHASE=$phase;EXIT_CODE=$rc"
    fi
    printf '%s\n' 'PROJECT_END=Gserver' '========== GACE_RESULT_END =========='
  }
  trap finish EXIT
  printf '%s\n' '========== GACE_RESULT_BEGIN ==========' 'PROJECT=Gserver' 'ACTION=WSL_DOCKER_COMPOSE_BOOTSTRAP' 'TARGET=LOCAL_WSL_ONLY'
  cd /mnt/g/Project/Gserver || { echo 'ERROR=GSERVER_ROOT_MISSING'; exit 10; }
  [[ -f app/gserver.py && ! -L app/gserver.py ]] || { echo 'ERROR=GSERVER_SOURCE_MISSING'; exit 11; }
  [[ "$(sha256sum app/gserver.py | cut -d' ' -f1)" == 41e0df51db854fd562f748b4f8dbcc558d0052d2d52d2957f6d3a89b9f61e15c ]] || { echo 'ERROR=SOURCE_SHA_CHANGED'; exit 24; }
  grep -Eqi '(microsoft|wsl)' /proc/sys/kernel/osrelease || { echo 'ERROR=NOT_WSL'; exit 12; }
  source /etc/os-release
  [[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] || { echo 'ERROR=UNSUPPORTED_OS'; exit 13; }
  [[ -d /run/systemd/system ]] || { echo 'ERROR=SYSTEMD_NOT_BOOTED'; exit 14; }
  [[ -z "${DOCKER_HOST:-}" ]] || { echo 'ERROR=EXISTING_DOCKER_HOST'; exit 15; }
  command -v sudo >/dev/null && command -v apt-get >/dev/null && command -v curl >/dev/null && command -v gpg >/dev/null || { echo 'ERROR=PREREQUISITE_COMMAND_MISSING'; exit 16; }
  if command -v docker >/dev/null || [[ -e /etc/apt/sources.list.d/docker.sources || -e /etc/apt/keyrings/docker.asc ]]; then
    echo 'ERROR=DOCKER_PREVIOUS_INSTALL_OR_REPO_FOUND'; exit 17
  fi
  for pkg in docker-ce docker-ce-cli docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd containerd.io runc; do
    state="$(dpkg-query -W '-f=${db:Status-Status}' "$pkg" 2>/dev/null || true)"
    if [[ "$state" == installed ]]; then echo "ERROR=CONFLICT_PACKAGE:$pkg"; exit 18; fi
  done
  before_podman="$(systemctl is-active podman.socket || true)"
  before_redis="$(systemctl is-active redis-server.service || true)"
  before_site="$(systemctl is-active site_total.service || true)"
  echo "BEFORE=podman.socket:$before_podman;redis:$before_redis;site_total:$before_site"
  sudo -v || { echo 'ERROR=SUDO_ACCESS_FAILED'; exit 19; }
  phase=REPOSITORY_KEY
  key_file="$(mktemp)"
  curl --proto '=https' --tlsv1.2 --connect-timeout 15 --max-time 60 -fsSL 'https://download.docker.com/linux/ubuntu/gpg' -o "$key_file"
  fingerprint="$(gpg --batch --show-keys --with-colons --fingerprint "$key_file" 2>/dev/null | awk -F: '$1=="fpr"{print $10;exit}')"
  [[ "$fingerprint" == '9DC858229FC7DD38854AE2D88D81803C0EBFCD88' ]] || { echo 'ERROR=DOCKER_KEY_FINGERPRINT_MISMATCH'; exit 20; }
  echo 'OFFICIAL_DOCKER_KEY=VERIFIED'
  phase=INSTALL_REPOSITORY
  sudo install -d -m 0755 /etc/apt/keyrings
  sudo install -m 0644 "$key_file" /etc/apt/keyrings/docker.asc
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: noble\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$(dpkg --print-architecture)" | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
  phase=APT_PREPARE
  sudo timeout 300 apt-get -o DPkg::Lock::Timeout=30 update -qq
  packages=(docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin)
  phase=APT_SIMULATION
  plan="$(sudo timeout 90 apt-get -o DPkg::Lock::Timeout=30 -s install "${packages[@]}")"
  if grep -Eq '^Remv |^Purg ' <<< "$plan"; then
    echo 'ERROR=APT_WOULD_REMOVE_INSTALLED_PACKAGES'
    grep -E '^Remv |^Purg ' <<< "$plan"
    exit 21
  fi
  echo "APT_INSTALL_COUNT=$(grep -c '^Inst ' <<< "$plan" || true);APT_REMOVE_COUNT=0"
  phase=INSTALL_DOCKER
  sudo timeout 900 env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=30 install -y -qq "${packages[@]}" >/dev/null
  phase=START_DOCKER
  sudo timeout 30 systemctl enable --now docker.service >/dev/null
  sudo timeout 15 docker info --format 'DOCKER_DAEMON={{.ServerVersion}}'
  sudo timeout 15 docker compose version
  phase=ISOLATED_SMOKE
  smoke_yaml=$'services:\n  smoke:\n    image: hello-world:latest\n    network_mode: none\n    read_only: true\n    security_opt:\n      - no-new-privileges:true\n    cap_drop:\n      - ALL\n'
  smoke="$(printf '%s' "$smoke_yaml" | sudo timeout 180 docker compose --project-name gace-docker-bootstrap -f - run --rm --no-deps smoke)"
  [[ "$smoke" == *'Hello from Docker!'* ]] || { echo 'ERROR=ISOLATED_SMOKE_NOT_CONFIRMED'; exit 22; }
  echo 'DOCKER_COMPOSE_SMOKE=PASS;PUBLISHED_PORTS=NONE'
  phase=REGRESSION
  after_podman="$(systemctl is-active podman.socket || true)"
  after_redis="$(systemctl is-active redis-server.service || true)"
  after_site="$(systemctl is-active site_total.service || true)"
  echo "AFTER=podman.socket:$after_podman;redis:$after_redis;site_total:$after_site"
  [[ "$after_podman" == "$before_podman" && "$after_redis" == "$before_redis" && "$after_site" == "$before_site" ]] || { echo 'ERROR=EXISTING_SERVICE_STATE_CHANGED'; exit 23; }
  echo 'PODMAN_REMOVED=NO;USER_ADDED_TO_DOCKER_GROUP=NO;OTHER_HOSTS_CHANGED=NO'
)
