#!/usr/bin/env bash
# One foreground verification unit; prompts only through the user's local sudo.
(
  set -Eeuo pipefail
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  phase=SOURCE
  finish() {
    result=$?
    trap - EXIT
    if (( result == 0 )); then
      echo 'VERIFY=PASS;SCOPE=ISOLATED_SOURCE_AND_PACKAGED_RUNTIME;F01_F08=NOT_COMPLETE'
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
  echo 'ACTION=PC_ISOLATED_RUNTIME_VERIFICATION'
  git diff --quiet
  git diff --cached --quiet
  git log -1 --format='SOURCE_SHA=%H'
  phase=LOCAL_TESTS
  python3 -m unittest discover -s tests -q
  bash -n scripts/smoke_gserver_staging.sh
  bash -n scripts/smoke_gserver_runtime.sh
  subcheck() {
    bash "$1" 2>&1 | sed -e '/^========== GACE_RESULT_/d' -e '/^PROJECT_END=/d' -e '/^PROJECT=/d' -e 's/^VERIFY=/SUBCHECK_VERIFY=/'
  }
  phase=EXISTING_SOURCE_STAGING
  subcheck scripts/smoke_gserver_staging.sh
  phase=PACKAGED_RUNTIME
  subcheck scripts/smoke_gserver_runtime.sh
)
