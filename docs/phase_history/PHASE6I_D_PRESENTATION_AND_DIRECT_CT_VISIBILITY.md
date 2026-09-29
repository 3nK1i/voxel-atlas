# Phase 6I-D — Presentation and Direct CT visibility

Scope: normal end-user 3D profile displays **Presentation**, without a profile-selection button group. The pre-existing internal `ReconstructionPresentationProfileController`, its `fidelity` and `presentation` definitions, lighting/material policies, and scientific qualification capabilities remain in place. The application requests `presentation` once during UI initialization; source geometry, opacity/structure state, reconstruction, segmentation, and clipping algorithms remain unchanged. The historical Phase 6E-A profile-button HTML contract is superseded only for the normal user interface, not for the internal profile catalog or scientific reference settings.

Direct CT visibility keeps the same native `<select>` element, values `all`, `hide-region-1`, and `hide-region-2`, and existing reversible `setRegionDisplayMode` event handling. CSS sets explicit theme-sensitive text/background colors for the closed selector and native popup options, legible disabled text, and a visible keyboard focus outline; it does not alter visibility, region classification, meshes, or source data.

## Acceptance

Run `bash scripts/run_phase6i_d_checks.sh` with the development `.venv` and existing scientific worker. In the local isolated browser (127.0.0.1:8011), confirm that Presentation is the only normal rendering profile; Surface and Combined retain their expected display; inspect the Direct CT visibility selector in both light and dark themes, closed and opened, including all three choices. Toggle hide region 1/2 and return to Full geometry to verify reversibility, without rebuilding. Perform a minimal clipping and MPR sanity check. If region separation is unavailable for the selected study, report this scenario as NOT TESTED, not PASS. The browser exercise does not establish clinical qualification or production readiness.

Historical test files that explicitly assert that *visible* Fidelity/Presentation buttons still exist describe the earlier Phase 6E interface and are not current user-facing UI acceptance criteria. The internal Fidelity implementation and its current scientific functionality remain unmodified.
