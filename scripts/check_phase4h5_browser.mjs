#!/usr/bin/env node
// Optional browser contract check with synthetic images; not patient/GPU validation.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(require.resolve("playwright", {
  paths: [process.cwd(), process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES].filter(Boolean),
}));
const root = new URL("../", import.meta.url);
const app = readFileSync(new URL("web/js/app.js", root), "utf8");
const html = readFileSync(new URL("web/index.html", root), "utf8");
const css = readFileSync(new URL("web/css/styles.css", root), "utf8");
const overlay = readFileSync(new URL("web/js/mpr-clipping-overlay.js", root), "utf8");
const fn = (name) => {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  return app.slice(start, app.indexOf("\nfunction ", start + 1));
};
const functions = ["clamp", "clippingPlaneRange", "clippingRangeIsActive", "setClippingControlsEnabled", "clippingBoundaryLpsMm",
  "clippingRequest", "applyPatientClipping", "syncClippingControlsFromMpr", "updateClippingBoundaryFromControl",
  "resetPatientClipping", "mprPhysicalMetrics", "configureMprSurface", "updateMprCrosshairOverlayForEntry",
  "updateMprClippingOverlays"].map(fn).join("\n");
const constants = app.slice(app.indexOf("const CLIPPING_PLANES ="), app.indexOf("const volumeRenderingPanel ="));
const events = app.slice(app.lastIndexOf("for (const [plane, controlsForPlane] of clippingRegistry.entries()) {"), app.indexOf("mprClippingOverlayToggle.addEventListener"));
assert.ok(events.includes("clippingResetButton.addEventListener"));
const out = mkdtempSync(join(tmpdir(), "voxelatlas-h5-browser-"));
const browser = await chromium.launch({ headless: true,
  ...(process.env.VOXELATLAS_BROWSER_EXECUTABLE ? { executablePath: process.env.VOXELATLAS_BROWSER_EXECUTABLE } : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/workspace") return route.fulfill({ contentType: "text/html", body: html.replace(/<script type="module"[^>]+><\/script>/, "") });
    if (path === "/css/styles.css") return route.fulfill({ contentType: "text/css", body: css });
    if (path === "/js/mpr-clipping-overlay.js") return route.fulfill({ contentType: "text/javascript", body: overlay });
    if (path === "/assets/logo.png") return route.fulfill({ contentType: "image/png", body: readFileSync(new URL("web/assets/logo.png", root)) });
    return route.abort();
  });
  await page.goto("http://h5.test/workspace");
  await page.evaluate(async ({ constants, functions, events }) => {
    const { projectMprClipping, renderMprClippingOverlay } = await import("/js/mpr-clipping-overlay.js");
    const run = new Function("projectMprClipping", "renderMprClippingOverlay", `
      const directionalCutPanel = document.getElementById('directionalCutPanel');
      const clippingResetButton = document.getElementById('clippingResetButton');
      const mprClippingOverlayToggle = document.getElementById('mprClippingOverlayToggle');
      const CLIPPING_MINIMUM_GAP_PERCENT = 0.1;
      const MPR_AXIS_INDEX = {x:0, y:1, z:2};
      ${constants}
      const planes = {};
      const ranges = {x:[-100,100], y:[-150,50], z:[-60,140]};
      const mprRegistry = new Map();
      for(const [plane, h, v, n] of [['axial','x','y','z'],['coronal','x','z','y'],['sagittal','y','z','x']]) {
        const p = { horizontal_axis:h, vertical_axis:v, normal_axis:n, vertical_reverse:plane!=='axial',
          horizontal_range_mm:ranges[h], vertical_range_mm:ranges[v], position_range_mm:ranges[n],
          image_width:200,image_height:200,pixel_spacing_mm:[1,1] };
        planes[plane]=p;
        const panel=document.querySelector('[data-mpr-plane="'+plane+'"]');
        panel.dataset.volumeState='ready';
        const surface=panel.querySelector('.mpr-image-surface');
        const canvas=surface.querySelector('canvas'); canvas.width=200;canvas.height=200;
        const ctx=canvas.getContext('2d');ctx.fillStyle='#222';ctx.fillRect(0,0,200,200);
        ctx.fillStyle='#aaa';ctx.beginPath();ctx.ellipse(100,100,65,85,0,0,Math.PI*2);ctx.fill();
        mprRegistry.set(plane,{panel,surface,view:surface.parentElement,canvas,renderedPlaneDescriptor:p,renderedPositionLpsMm:0});
      }
      const state={clipping:{axial:{enabled:false,startPercent:0,endPercent:100},coronal:{enabled:false,startPercent:0,endPercent:100},sagittal:{enabled:false,startPercent:0,endPercent:100}},mpr:{descriptor:{planes},crosshairLpsMm:[0,0,0]}};
      const volumeLayer={available:true};
      const volumeRayMarcher={current:{},setClippingPlanes:(r)=>r};
      const volumeRenderingQuality={pulseInteraction:()=>{}};
      const requestViewerRender=()=>{};
      const syncSliceRenderingControlsFromMpr=()=>{};
      ${functions}
      ${events}
      mprClippingOverlayToggle.addEventListener('change',updateMprClippingOverlays);
      const resize=()=>{for(const [plane,entry] of mprRegistry)configureMprSurface(entry,planes[plane]);};
      const observer=new ResizeObserver(resize);for(const entry of mprRegistry.values())observer.observe(entry.view);
      syncClippingControlsFromMpr();resize();
      window.h5={state,mprRegistry,resize};
    `);
    run(projectMprClipping, renderMprClippingOverlay);
  }, { constants, functions, events });
  const pixelsBefore = await page.locator("#mprAxialCanvas").evaluate((c) => c.toDataURL());
  for (const axis of ["axial", "coronal", "sagittal"]) {
    for (const [boundary, value] of [["start", "25"], ["end", "75"]]) {
      await page.locator(`[data-clip-${boundary}="${axis}"]`).evaluate((el, val) => {
        el.value = val; el.dispatchEvent(new Event("input", { bubbles: true }));
      }, value);
    }
  }
  assert.equal(await page.locator(".mpr-clipping-overlay:visible").count(), 3);
  assert.equal(await page.locator("#mprAxialCanvas").evaluate((c) => c.toDataURL()), pixelsBefore);
  assert.deepEqual(await page.evaluate(() => window.h5.state.mpr.crosshairLpsMm), [0, 0, 0]);
  for (const width of [1920, 1366, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => window.h5.resize());
    for (const theme of ["dark", "light"]) {
      await page.evaluate((t) => document.documentElement.dataset.theme = t, theme);
      const metrics = await page.evaluate(() => {
        const selectors = ['.clip-range-summary strong','.clip-boundary-labels span','.clip-boundary-values strong'];
        return selectors.flatMap((s) => [...document.querySelectorAll(s)].map((el) => {
          const rect=el.getBoundingClientRect(), parent=el.closest('.clip-plane-control').getBoundingClientRect();
          return {size:parseFloat(getComputedStyle(el).fontSize), fits:rect.left>=parent.left && rect.right<=parent.right+1};
        }));
      });
      assert.ok(metrics.every((m) => m.size >= 11 && m.fits), `${width}/${theme} labels`);
      for (const plane of ["axial", "coronal", "sagittal"]) {
        const [a,b] = await page.locator(`[data-mpr-surface="${plane}"]`).evaluate((el)=>[
          el.querySelector('canvas'),el.querySelector('svg'),
        ].map((n)=>{const r=n.getBoundingClientRect();return [r.x,r.y,r.width,r.height];}));
        a.forEach((v,i)=>assert.ok(Math.abs(v-b[i]) < 1, `${width}/${theme} image registration`));
      }
      if(width===1366) await page.locator("#directionalCutPanel").screenshot({path:join(out,`clipping-${theme}.png`)});
    }
  }
  await page.setViewportSize({width:1366,height:900});
  await page.evaluate(()=>{document.documentElement.dataset.theme='dark';window.h5.resize();});
  await page.locator('.mpr-grid').screenshot({path:join(out,'mpr-synthetic.png')});
  await page.locator('#mprClippingOverlayToggle').uncheck();
  assert.equal(await page.locator('.mpr-clipping-overlay:visible').count(),0);
  await page.locator('#mprClippingOverlayToggle').check();
  assert.equal(await page.locator('.mpr-clipping-overlay:visible').count(),3);
  await page.locator('#clippingResetButton').click();
  assert.equal(await page.locator('.mpr-clipping-overlay:visible').count(),0);
  assert.equal(await page.locator('#mprAxialCanvas').evaluate((c)=>c.toDataURL()),pixelsBefore);
  assert.deepEqual(errors,[]);
  console.log('PHASE4H5_BROWSER_SYNTHETIC_CHECK=PASS');
  console.log(`SCREENSHOTS=${out}`);
} finally { await browser.close(); }
