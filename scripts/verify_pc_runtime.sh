#!/usr/bin/env bash
# One foreground verification unit; prompts only through the user's local sudo.
(
  set -Eeuo pipefail
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
  phase=SOURCE
  source_sha=UNKNOWN
  finish() {
    result=$?
    trap - EXIT
    final_source="$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
    if (( result == 0 )) && { [[ "$source_sha" != "$final_source" ]] || ! git diff --quiet || ! git diff --cached --quiet; }; then
      result=35
      phase=SOURCE_CHANGED
    fi
    if ! python3 scripts/runtime_evidence.py "$source_sha" "$final_source" "$phase" "$result"; then
      result=34
      phase=EVIDENCE_WRITE
    fi
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
  source_sha="$(git rev-parse HEAD)"
  git diff --quiet
  git diff --cached --quiet
  git log -1 --format='SOURCE_SHA=%H'
  phase=LOCAL_TESTS
  python3 -m unittest discover -s tests -q
  if command -v node >/dev/null 2>&1; then
    node tests/test_ui.cjs
  elif command -v node.exe >/dev/null 2>&1; then
    node.exe tests/test_ui.cjs
  else
    echo 'UI_BEHAVIOR_TESTS=NOT_RUN;REASON=NODE_NOT_AVAILABLE'
  fi
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
