#!/usr/bin/env bash
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0

run_check() {
    local label="$1"
    shift
    echo
    echo "===== $label ====="
    if "$@"; then
        echo "${label}_RC=0"
    else
        local rc=$?
        echo "${label}_RC=$rc"
        FAIL=1
    fi
}

run_check "PHASE0C1_REGRESSION" \
    bash scripts/run_phase0c1_checks.sh

run_check "PHASE0C2_UNIT" \
    python3 -m unittest discover -s tests -p 'test_phase0c2_environment_contract.py' -v

run_check "PHASE0C2_CORE_ENV" \
    python3 scripts/check_phase0c2_environment.py --profile core

echo
echo "===== PHASE 0C2 RESULT ====="
if [ "$FAIL" -eq 0 ]; then
    echo "PHASE0C2_FOUNDATION_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE0C2_FOUNDATION_CHECKS_OK=NO"
exit 1
