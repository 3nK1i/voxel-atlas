#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo "===== CT-B1 THREE-DIMENSIONAL COLOR ISOLATION ====="
node --check web/js/reconstruction-surface-presentation.js
node --check web/js/segmentation-surface-viewer.js
node scripts/check_ct_b1_3d_color_isolation.mjs

echo "===== PREVIOUS PHASE 6I INTEGRATED REGRESSIONS ====="
bash scripts/run_phase6i_integrated_ergonomics_checks.sh

echo "===== FINAL DIFF ====="
git diff --check
git diff --cached --check
echo "CTB1_CHECKS_OK=YES"
