#!/usr/bin/env node

import assert from "node:assert/strict";

import {
  classifySampleStudyActivation,
} from "../web/js/sample-study-activation.js";


assert.equal(
  classifySampleStudyActivation({
    study: {
      study_id: "a".repeat(32),
      reconstruction_ready: true,
      volume_ready: true,
    },
  }),
  "restore",
);
assert.equal(
  classifySampleStudyActivation({
    study: {
      study_id: "b".repeat(32),
      reconstruction_ready: true,
      volume_ready: false,
    },
  }),
  "construct",
);
assert.equal(
  classifySampleStudyActivation({
    study: {
      study_id: "c".repeat(32),
      reconstruction_ready: false,
      volume_ready: false,
    },
  }),
  "review",
);
assert.throws(
  () => classifySampleStudyActivation({}),
  /incomplete/i,
);

console.log("PHASE5F2_READY_SAMPLE_RESTORATION=PASS");
console.log("PHASE5F2_UNBUILT_SAMPLE_CONSTRUCTION=PASS");
console.log("PHASE5F2_UNQUALIFIED_SAMPLE_REVIEW=PASS");
console.log("PHASE5F2_SAMPLE_STUDY_SWITCH_CONTRACT_OK=YES");
