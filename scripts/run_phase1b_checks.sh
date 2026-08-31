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

run_step "PHASE1A_REGRESSION" bash scripts/run_phase1a_checks.sh || failed=1
run_step "PHASE1B_BACKEND_ENV" python3 scripts/check_phase1b_backend_environment.py || failed=1
run_step "PHASE1B_UNIT" python3 -m unittest discover -s tests -p 'test_phase1b_auth_http_contract.py' -v || failed=1
run_step "PHASE1B_HTTP_PROBE" python3 scripts/check_phase1b_auth_http.py || failed=1

run_step "PHASE1B_PYTHON_AST" python3 - <<'PY' || failed=1
from pathlib import Path
import ast

paths = sorted(Path("backend/voxelatlas").glob("*.py"))
paths += [
    Path("scripts/check_phase1b_backend_environment.py"),
    Path("scripts/check_phase1b_auth_http.py"),
    Path("tests/test_phase1b_auth_http_contract.py"),
]
for path in paths:
    ast.parse(path.read_text(encoding="utf-8"))
print(f"PHASE1B_PYTHON_AST_OK=YES files={len(paths)}")
PY

echo
echo "===== PHASE 1B RESULT ====="
if [ "$failed" -eq 0 ]; then
    echo "PHASE1B_AUTH_HTTP_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE1B_AUTH_HTTP_CHECKS_OK=NO"
exit 1
