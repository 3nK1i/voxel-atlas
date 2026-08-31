#!/usr/bin/env bash
set -u

run_step() {
    local label="$1"
    shift
    echo
    echo "===== ${label} ====="
    "$@"
    local rc=$?
    echo "${label}_RC=${rc}"
    return "$rc"
}

failed=0

run_step "PHASE1B_REGRESSION" bash scripts/run_phase1b_checks.sh || failed=1
run_step "PHASE1C_UNIT" python3 -m unittest discover -s tests -p 'test_phase1c_login_ui_contract.py' -v || failed=1
run_step "PHASE1C_LOGIN_PROBE" python3 scripts/check_phase1c_login_ui.py || failed=1

run_step "PHASE1C_PYTHON_AST" python3 - <<'PY' || failed=1
from pathlib import Path
import ast

paths = [
    Path("backend/voxelatlas/app.py"),
    Path("scripts/check_phase1c_login_ui.py"),
    Path("tests/test_phase1c_login_ui_contract.py"),
]
for path in paths:
    ast.parse(path.read_text(encoding="utf-8"))
print(f"PHASE1C_PYTHON_AST_OK=YES files={len(paths)}")
PY

run_step "PHASE1C_JAVASCRIPT_SYNTAX" node --check web/js/login.js || failed=1

echo
echo "===== PHASE 1C RESULT ====="
if [ "$failed" -eq 0 ]; then
    echo "PHASE1C_LOGIN_UI_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE1C_LOGIN_UI_CHECKS_OK=NO"
exit 1
