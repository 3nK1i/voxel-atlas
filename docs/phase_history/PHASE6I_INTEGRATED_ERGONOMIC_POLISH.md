# Phase 6I — focused ergonomic polish before integrated closure

## Baseline and purpose

Apply only after the Phase 6I-D commit `525e23259563421641a895d631d12fa6a0725dc5` on `phase6-accurate-surfaces`. The six previous 6I implementation substeps are not reopened. This change addresses two concrete user-reported visual alignment issues from the local desktop review.

## Scope

- Right-side Direct CT Surface controls: `CT isovalue` and `Direct CT visibility` now have an inline, non-wrapping title containing their own existing contextual `?` control. The explanation text remains below each label.
- The unchanged numeric `volumeSurfaceIsovalue` input and its `HU` unit now share one distinct, theme-aware visual container. The field remains an editable number with the same `id`, `step`, initial value, disabled state, input events, and source-threshold behavior. The container's focus ring encloses the field and unit.
- Left-sidebar Volume, Surface, and Combined mode cards occupy the same width and vertical footprint they did before contextual help was added. Each separate keyboard-focusable `?` is positioned **inside the card outline**, without nesting it inside its native mode button. The existing checkmark has a reserved slot; disabled mode buttons do not disable the sibling help control.
- Refresh only the CSS and contextual-help module asset versions. No change to app.js, backend, datasets, CT/surface geometry, segmentation, rendering, clipping, profile behavior, or any help explanation.

## Validation scope

Run `bash scripts/run_phase6i_integrated_ergonomics_checks.sh`. This tests the new layout contract and previously validated 6I-D/C/B/A source and scientific regression gates and checks JS syntax and Git whitespace.

In the isolated local development browser at `127.0.0.1:8011`, with an existing local CT study: verify all three mode cards keep the prior full width, look aligned, and have an independent help icon *inside* each card; clicking / keyboard-opening help does not switch modes, including when a mode button is disabled. Verify that CT isovalue and Direct CT visibility display inline help, and that the `300 HU` value is in one legible capsule without truncation or breaking the input's numeric editing. Confirm the opened help popup, native dropdown, Volume/Surface/Combined, and one reversible Direct CT visibility change still work. Inspect dark/light themes and the user's 1366×768 viewport. Do not upload patient data or carry out production operations for this UI test.

The isolated source-contract tests do not replace the browser interaction review or imply clinical, real-study fidelity, or production qualification.
