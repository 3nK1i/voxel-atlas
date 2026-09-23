#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo '===== CT-B3A ANATOMICAL PALETTE COMPLETION ====='
node --check web/js/segmentation-anatomical-appearance.js
node --check web/js/app.js
node --check scripts/check_ct_b3a_anatomical_palette.mjs
node scripts/check_ct_b3a_anatomical_palette.mjs
echo '===== CT-B2, CT-B1, PHASE 6I AND SCIENTIFIC REGRESSIONS ====='
bash scripts/run_ct_b2_checks.sh
git diff --check
git diff --cached --check
echo 'CTB3A_CHECKS_OK=YES'
