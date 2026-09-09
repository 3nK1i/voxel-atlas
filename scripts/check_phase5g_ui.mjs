#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../web/css/styles.css", import.meta.url), "utf8");
const app = readFileSync(new URL("../web/js/app.js", import.meta.url), "utf8");

assert(!html.includes('id="anatomicalLayersPanel"'));
assert(!html.includes('id="volumeLayerButton"'));
assert(!html.includes('id="anatomyNote"'));
assert(!app.includes("volumeLayerButton"));
assert(!app.includes("anatomyNote"));

const accountZone = html.match(/<div class="account-zone">([\s\S]*?)<\/div>\s*<\/header>/)?.[1] ?? "";
assert(accountZone.indexOf('id="themeToggle"') >= 0);
assert(accountZone.indexOf('id="themeToggle"') < accountZone.indexOf('class="account"'));
assert.equal((html.match(/id="themeToggle"/g) ?? []).length, 1);
assert(html.includes('class="theme-icon theme-icon-sun"'));
assert(html.includes('class="theme-icon theme-icon-moon"'));
assert(app.includes('themeToggle.setAttribute(\n    "title",'));

assert(html.includes('<span id="uploadDicomLabel">Upload DICOM</span>'));
assert(!app.includes('"Replace DICOM Study"'));
assert(!app.includes("Uploading ${files.length}"));
assert(css.includes(".upload-button {"));
assert(css.includes("justify-content: center;"));
assert(css.includes("text-align: center;"));

for (const selector of [
  ".clip-plane-heading strong",
  ".clip-range-summary",
  ".clip-boundary-labels",
  ".clip-boundary-values strong",
  ".clip-plane-toggle",
  ".mpr-clipping-toggle",
  ".mpr-clipping-legend",
]) assert(css.includes(selector));
assert(!/\.mpr-clipping-(?:toggle|legend)\s*\{[^}]*font-size:\s*12px/s.test(css));
assert(html.includes("phase5g-r1"));

console.log("PHASE5G_UI_CONTRACT_OK=YES");
