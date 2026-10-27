#!/usr/bin/env bash
# Run focused help-contract checks and the preceding regression gate.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo '===== PHASE 6I-A CONTEXTUAL HELP CONTRACT ====='
.venv/bin/python -m unittest discover -s tests -p 'test_phase6i_a_contextual_help_contract.py' -v
echo 'PHASE6I_A_CONTRACT=PASS'

echo '===== PHASE 6I-A JAVASCRIPT SYNTAX ====='
if command -v node >/dev/null 2>&1; then
    node --check web/js/parameter-help.js
    echo 'PHASE6I_A_JS_SYNTAX=PASS'
else
    echo 'PHASE6I_A_JS_SYNTAX=NOT_RUN_NODE_UNAVAILABLE'
fi

echo '===== PHASE 6I-A PRIOR PHASE REGRESSION ====='
# The historical 6H-C script is a pre-commit exact-candidate guard pinned to
# an older HEAD; do not invoke it after Phase I.6 was closed. Run its durable
# documentation tests and the 6H-A/6G synthetic regression directly instead.
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python}"
test -x "$PYTHON"
"$PYTHON" -m unittest discover -s tests -p 'test_phase6h_c_closure_contract.py' -q
VOXELATLAS_SURFACE_PYTHON="$PYTHON" bash scripts/run_phase6h_a_checks.sh
echo 'PHASE6I_A_REGRESSION=PASS'

echo '===== PHASE 6I-A GIT WHITESPACE ====='
git diff --check
echo 'PHASE6I_A_CANDIDATE_CHECKS_OK=YES'
