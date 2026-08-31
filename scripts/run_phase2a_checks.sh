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

run_check "PHASE1C_REGRESSION" bash scripts/run_phase1c_checks.sh
run_check "PHASE2A_UNIT" python3 -m unittest discover -s tests -p 'test_phase2a_va_workspace_migration.py' -v
run_check "PHASE2A_WORKSPACE_PROBE" python3 scripts/check_phase2a_va_workspace.py

echo
echo "===== PHASE2A JAVASCRIPT SYNTAX ====="
if node --check web/js/app.js; then
    echo "PHASE2A_JAVASCRIPT_SYNTAX_RC=0"
else
    rc=$?
    echo "PHASE2A_JAVASCRIPT_SYNTAX_RC=$rc"
    FAIL=1
fi

echo
echo "===== PHASE2A PYTHON AST ====="
if python3 - <<'PY'
from pathlib import Path
import ast
paths = [Path("scripts/check_phase2a_va_workspace.py"), Path("tests/test_phase2a_va_workspace_migration.py")]
for path in paths:
    ast.parse(path.read_text(encoding="utf-8"))
print(f"PHASE2A_PYTHON_AST_OK=YES files={len(paths)}")
PY
then
    echo "PHASE2A_PYTHON_AST_RC=0"
else
    rc=$?
    echo "PHASE2A_PYTHON_AST_RC=$rc"
    FAIL=1
fi

echo
echo "===== PHASE 2A RESULT ====="
if [ "$FAIL" -eq 0 ]; then
    echo "PHASE2A_VA_WORKSPACE_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE2A_VA_WORKSPACE_CHECKS_OK=NO"
exit 1
