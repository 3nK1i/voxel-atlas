#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo '===== CT-B2 ANATOMICAL APPEARANCE ====='
node --check web/js/segmentation-anatomical-appearance.js
node --check web/js/app.js
node --check web/js/segmentation-surface-viewer.js
node scripts/check_ct_b2_anatomical_appearance.mjs
echo '===== PRIOR CT-B1 AND PHASE 6I REGRESSIONS ====='
bash scripts/run_ct_b1_checks.sh
git diff --check
git diff --cached --check
echo 'CTB2_CHECKS_OK=YES'
