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

run_check "PHASE0C1_INTEGRITY" python3 scripts/check_phase0c1_baseline_integrity.py
run_check "PHASE0C1_UNIT" python3 -m unittest discover -s tests -p 'test_phase0c1_baseline_contract.py' -v

echo
echo "===== PYTHON AST ====="
if python3 - <<'PY'
from pathlib import Path
import ast

files = sorted(Path("scripts").glob("*.py"))
for path in files:
    ast.parse(path.read_text(encoding="utf-8"))
print(f"PYTHON_AST_OK=YES files={len(files)}")
PY
then
    echo "PYTHON_AST_RC=0"
else
    rc=$?
    echo "PYTHON_AST_RC=$rc"
    FAIL=1
fi

echo
echo "===== JAVASCRIPT SYNTAX ====="
if command -v node >/dev/null 2>&1; then
    echo "NODE=$(node --version)"
    if node --check web/js/app.js; then
        echo "PASS web/js/app.js"
    else
        echo "FAIL web/js/app.js"
        FAIL=1
    fi
else
    echo "NODE_AVAILABLE=NO"
    FAIL=1
fi

echo
echo "===== RAW MEDICAL DATA GIT SANITY ====="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    raw_files="$(git ls-files | grep -Ei '\.(dcm|nii|nii\.gz|nrrd)$' || true)"
    if [ -n "$raw_files" ]; then
        echo "$raw_files"
        echo "RAW_MEDICAL_FILES_TRACKED=YES"
        FAIL=1
    else
        echo "RAW_MEDICAL_FILES_TRACKED=NO"
    fi
else
    echo "GIT_WORK_TREE=NO (tracking check skipped)"
fi

echo
echo "===== PHASE 0C1 RESULT ====="
if [ "$FAIL" -eq 0 ]; then
    echo "PHASE0C1_BASELINE_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE0C1_BASELINE_CHECKS_OK=NO"
exit 1
