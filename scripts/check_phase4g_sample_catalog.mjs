#!/usr/bin/env node
import assert from "node:assert/strict";

import {
  SampleStudyCatalogClient,
  normalizeSampleCatalog,
} from "../web/js/sample-study-catalog.js";


const normalized = normalizeSampleCatalog({
  samples: [
    {
      sample_id: "mr-brain",
      title: "Brain MR",
      summary: "Deidentified demonstration study.",
      modality: "MR",
      body_region: "Head",
      source_label: "Public archive",
      source_url: "https://example.org/source",
      license_label: "Source terms",
      license_url: "https://example.org/license",
      file_count: 112,
      size_bytes: 24000000,
      featured: true,
      preview_available: true,
      preview_url: "/api/sample-studies/mr-brain/preview",
    },
    {
      sample_id: "ct-chest",
      title: "Chest CT",
      summary: "Deidentified demonstration study.",
      modality: "CT",
      body_region: "Chest",
      source_label: "Public archive",
      source_url: "https://example.org/source",
      license_label: "Source terms",
      license_url: "https://example.org/license",
      file_count: 101,
      size_bytes: 18000000,
      featured: false,
      preview_available: false,
      preview_url: null,
    },
  ],
});
assert.equal(normalized.length, 2);
assert.equal(normalized[0].sampleId, "mr-brain");
assert.equal(normalized[0].modality, "MR");
assert.equal(normalized[1].previewUrl, null);
assert.ok(Object.isFrozen(normalized));
assert.ok(Object.isFrozen(normalized[0]));

assert.throws(
  () => normalizeSampleCatalog({ samples: [{ sample_id: "../private" }] }),
  /invalid/i,
);
assert.throws(
  () => normalizeSampleCatalog({
    samples: [{ ...normalized[0], sample_id: "ct-head", source_url: "file:///private" }],
  }),
  /invalid/i,
);

const requests = [];
const fakeFetch = async (url, options = {}) => {
  requests.push({ url, options });
  if (url === "/api/sample-studies") {
    return {
      ok: true,
      json: async () => ({ samples: [] }),
    };
  }
  return {
    ok: true,
    json: async () => ({
      sample: {
        sample_id: "ct-head",
        title: "Head CT",
        summary: "Deidentified demonstration study.",
        modality: "CT",
        body_region: "Head",
        source_label: "Public archive",
        source_url: "https://example.org/source",
        license_label: "Source terms",
        license_url: "https://example.org/license",
        file_count: 100,
        size_bytes: 20000000,
        featured: true,
        preview_available: false,
        preview_url: null,
      },
      study: { study_id: "loaded" },
    }),
  };
};

const client = new SampleStudyCatalogClient({ fetchImpl: fakeFetch });
assert.deepEqual(await client.list(), []);
const loaded = await client.load("ct-head");
assert.equal(loaded.study.study_id, "loaded");
assert.equal(requests[0].options.credentials, "same-origin");
assert.equal(requests[1].options.method, "POST");
assert.equal(requests[1].options.credentials, "same-origin");
assert.equal(requests[1].url, "/api/sample-studies/ct-head/load");

const originalFetch = globalThis.fetch;
let nativeFetchReceiver = null;
try {
  globalThis.fetch = async function boundFetchProbe() {
    nativeFetchReceiver = this;
    return {
      ok: true,
      json: async () => ({ samples: [] }),
    };
  };
  const nativeClient = new SampleStudyCatalogClient();
  assert.deepEqual(await nativeClient.list(), []);
  assert.equal(nativeFetchReceiver, globalThis);
} finally {
  globalThis.fetch = originalFetch;
}

console.log("PHASE4G_SAMPLE_STUDY_CATALOG=PASS");
