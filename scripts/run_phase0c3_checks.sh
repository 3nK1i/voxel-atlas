#!/usr/bin/env bash
set -u

fail=0

echo "===== PHASE0C2_REGRESSION ====="
bash scripts/run_phase0c2_checks.sh
PHASE0C2_REGRESSION_RC=$?
echo "PHASE0C2_REGRESSION_RC=$PHASE0C2_REGRESSION_RC"
if [ "$PHASE0C2_REGRESSION_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE0C3_UNIT ====="
python3 -m unittest discover \
  -s tests \
  -p 'test_phase0c3_application_security_contract.py' \
  -v
PHASE0C3_UNIT_RC=$?
echo "PHASE0C3_UNIT_RC=$PHASE0C3_UNIT_RC"
if [ "$PHASE0C3_UNIT_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE0C3_FOUNDATION ====="
python3 scripts/check_phase0c3_foundation.py
PHASE0C3_FOUNDATION_RC=$?
echo "PHASE0C3_FOUNDATION_RC=$PHASE0C3_FOUNDATION_RC"
if [ "$PHASE0C3_FOUNDATION_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE0C3 PYTHON AST ====="
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
print(f"PHASE0C3_PYTHON_AST_OK=YES files={len(files)}")
PY
PHASE0C3_AST_RC=$?
echo "PHASE0C3_AST_RC=$PHASE0C3_AST_RC"
if [ "$PHASE0C3_AST_RC" -ne 0 ]; then
    fail=1
fi

echo
echo "===== PHASE 0C3 RESULT ====="
if [ "$fail" -eq 0 ]; then
    echo "PHASE0C3_FOUNDATION_CHECKS_OK=YES"
    exit 0
fi

echo "PHASE0C3_FOUNDATION_CHECKS_OK=NO"
exit 1
