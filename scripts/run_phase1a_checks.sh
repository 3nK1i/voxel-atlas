#!/usr/bin/env bash
set -u

fail=0

echo "===== PHASE0C3_REGRESSION ====="
bash scripts/run_phase0c3_checks.sh
PHASE0C3_REGRESSION_RC=$?
echo "PHASE0C3_REGRESSION_RC=$PHASE0C3_REGRESSION_RC"
if [ "$PHASE0C3_REGRESSION_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE1A_UNIT ====="
python3 -m unittest discover \
  -s tests \
  -p 'test_phase1a_authentication_core.py' \
  -v
PHASE1A_UNIT_RC=$?
echo "PHASE1A_UNIT_RC=$PHASE1A_UNIT_RC"
if [ "$PHASE1A_UNIT_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE1A_CORE_PROBE ====="
python3 scripts/check_phase1a_authentication_core.py
PHASE1A_CORE_RC=$?
echo "PHASE1A_CORE_RC=$PHASE1A_CORE_RC"
if [ "$PHASE1A_CORE_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE1A PYTHON AST ====="
python3 - <<'PY'
from pathlib import Path
import ast

roots = [Path("backend"), Path("scripts"), Path("tests")]
files = sorted(
    path
    for root in roots
    if root.exists()
    for path in root.rglob("*.py")
)
for path in files:
    ast.parse(path.read_text(encoding="utf-8"))
print(f"PHASE1A_PYTHON_AST_OK=YES files={len(files)}")
PY
PHASE1A_AST_RC=$?
echo "PHASE1A_AST_RC=$PHASE1A_AST_RC"
if [ "$PHASE1A_AST_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE 1A RESULT ====="
if [ "$fail" -eq 0 ]; then
    echo "PHASE1A_AUTHENTICATION_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE1A_AUTHENTICATION_CHECKS_OK=NO"
exit 1
