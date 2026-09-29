#!/usr/bin/env node

import assert from "node:assert/strict";
import { validateCorrectionDraftAction } from "../web/js/segmentation-correction-panel.js";


const action = validateCorrectionDraftAction({
  kind: "exclude",
  label_id: 91,
  center_lps_mm: [-2.5, 18.25, 104.0],
  radius_mm: 3,
  plane: "axial",
});
assert.deepEqual(action.center_lps_mm, [-2.5, 18.25, 104]);
assert.equal(action.label_id, 91);
assert.throws(
  () => validateCorrectionDraftAction({ ...action, radius_mm: 30 }),
  /invalid/,
);
assert.throws(
  () => validateCorrectionDraftAction({ ...action, center_lps_mm: [1, 2] }),
  /invalid/,
);
assert.throws(
  () => validateCorrectionDraftAction({ ...action, kind: "commit" }),
  /invalid/,
);

console.log("PHASE5F2_PATIENT_LPS_ACTION_VALIDATION=PASS");
console.log("PHASE5F2_RADIUS_BOUNDARY=PASS");
console.log("PHASE5F2_UNSUPPORTED_ACTION_REJECTION=PASS");
console.log("PHASE5F2_BROWSER_CONTRACT_OK=YES");
