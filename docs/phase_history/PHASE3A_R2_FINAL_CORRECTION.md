# Phase 3A-R2 - Final Correction

This correction closes the last presentation issues observed during R2 manual validation. It remains a viewer-only change and does not modify DICOM ingestion, storage, authentication, or reconstruction state.

## Scope

- preserve the qualified `web/assets/logo.png` bytes while using dark-theme CSS lighten blending so the dark image canvas visually merges with the workspace header instead of appearing as a square tile
- lower the desktop S/A/R/L gizmo by 14 px so the visible cube/labels align more closely with the interaction helper
- preserve the transparent gizmo container and the R2 anatomical axis arrowheads
- preserve direct 0-100% opacity semantics
- apply a perceptual clinical alpha curve for intermediate values so 40-70% remains visibly transparent without exposing as much of the temporary demo mesh's overlapping internal geometry
- preserve exact endpoints: 100% is fully opaque and 0% hides the anatomy
- preserve the accepted approximately 15% smaller initial framing

## Safety

The authoritative logo file is not edited or replaced. The final logo correction is presentation-only and therefore keeps the previously qualified asset fingerprint intact.

The alpha curve affects only display opacity. The UI value remains the user's direct 0-100% opacity control and remains monotonic.
