#!/usr/bin/env bash
# Source-only synthetic regression and exact-candidate review.
# No real-study access, worker execution, network calls, commit, or push.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

EXPECTED_HEAD=44f5a59c50fc893f309769d1661120955b44f778
EXPECTED_BRANCH=phase6-accurate-surfaces
PYTHON="${VOXELATLAS_SURFACE_PYTHON:-}"

printf '===== PHASE6H_C_CHECKPOINT_GUARD =====\n'
test "$(git branch --show-current)" = "$EXPECTED_BRANCH"
test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"
test "$(git rev-parse "origin/$EXPECTED_BRANCH")" = "$EXPECTED_HEAD"
git diff --quiet
git diff --cached --quiet
test -n "$PYTHON" && test -x "$PYTHON"

expected_files="$(printf '%s\n' \
  docs/phase_history/PHASE6H_C_SCOPED_QUALIFICATION_AND_I6_CLOSURE.md \
  scripts/run_phase6h_c_closure_checks.sh \
  tests/test_phase6h_c_closure_contract.py | LC_ALL=C sort)"
actual_files="$(git ls-files --others --exclude-standard | LC_ALL=C sort)"
test "$actual_files" = "$expected_files"
for file in $expected_files; do
  test -f "$file"
  if LC_ALL=C grep -nE '[[:blank:]]+$' "$file"; then
    printf 'PHASE6H_C_WHITESPACE=FAIL\n' >&2
    exit 1
  fi
done
printf 'PHASE6H_C_EXACT_CANDIDATE=PASS\n'

printf '\n===== PHASE6H_C_DOCUMENTATION_CONTRACT =====\n'
"$PYTHON" -m unittest discover -s tests -p test_phase6h_c_closure_contract.py -q
printf 'PHASE6H_C_DOCUMENTATION_CONTRACT=PASS\n'

printf '\n===== PHASE6H_A_AND_6G_REGRESSION =====\n'
VOXELATLAS_SURFACE_PYTHON="$PYTHON" bash scripts/run_phase6h_a_checks.sh

printf '\n===== PHASE6H_C_SYNTAX_AND_FINAL_GIT_SAFETY =====\n'
bash -n scripts/run_phase6h_c_closure_checks.sh
"$PYTHON" -m py_compile tests/test_phase6h_c_closure_contract.py
git diff --check
git diff --cached --check
git diff --quiet
git diff --cached --quiet
test "$(git ls-files --others --exclude-standard | LC_ALL=C sort)" = "$expected_files"
printf 'PHASE6H_C_CANDIDATE_CHECKS_OK=YES\n'
printf 'PHASE_I6_PRODUCTION_DEPLOYMENT=NOT_PERFORMED\n'
