#!/usr/bin/env bash
set -u -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

run_quiet() {
    local label="$1"
    shift
    local log="$TMP_DIR/${label}.log"
    if "$@" >"$log" 2>&1; then
        printf '%-34s PASS\n' "$label"
    else
        local rc=$?
        printf '%-34s FAIL (rc=%s)\n' "$label" "$rc"
        echo "----- ${label} diagnostic -----"
        cat "$log"
        echo "----- end diagnostic -----"
        FAIL=1
    fi
}

echo "===== PHASE 2B COMPACT VALIDATION ====="
run_quiet "Phase 2A regression" bash scripts/run_phase2a_checks.sh
run_quiet "Phase 2B unit contract" python3 -m unittest discover -s tests -p 'test_phase2b_final_workspace_target.py' -v
run_quiet "Phase 2B workspace probe" python3 scripts/check_phase2b_final_workspace.py
run_quiet "JavaScript syntax" bash -c 'node --check web/js/app.js && node --check web/js/login.js'
run_quiet "Python AST" python3 -c 'from pathlib import Path; import ast; [ast.parse(p.read_text(encoding="utf-8")) for p in (Path("scripts/check_phase2b_final_workspace.py"), Path("tests/test_phase2b_final_workspace_target.py"))]'
run_quiet "Retired feature scan" bash -c '! grep -RInE --exclude="*.png" --exclude="*.glb" --exclude-dir="__pycache__" "cranial|aperture|cutaway|openingSlider|openingValue|openingDescription|skull_open" web backend'
run_quiet "Em-dash scan" bash -c '! grep -RIn --exclude="*.png" --exclude="*.glb" --exclude-dir="__pycache__" "—" web backend'
run_quiet "Diff whitespace" git diff --check

echo
if [[ "$FAIL" -eq 0 ]]; then
    echo "PHASE2B_FINAL_WORKSPACE_CHECKS_OK=YES"
    echo "TEST_RC=0"
    exit 0
fi

echo "PHASE2B_FINAL_WORKSPACE_CHECKS_OK=NO"
echo "TEST_RC=1"
exit 1
