# Post-D6 — Sample catalog polish and MRI presentation initialization

Authoritative base: `3dca980` on `phase6-accurate-surfaces` after Phase 6J-D closure.

## Scope

This is a narrow presentation/ergonomics update before Phase 6J-E. It does not change MRI normalization, Patient-LPS geometry, segmentation behavior, sample-study ingestion/integrity verification, or the Direct CT backend.

- The sample gallery replaces text-only `CT` / `MR` fallback monograms with the approved CT and MR SVG artwork under `web/assets/`.
- Sample-card action text is shortened from **Open in VoxelAtlas** to **Open**.
- The browser-only **Replace the current workspace?** confirmation flow is removed. Selecting **Open** starts the existing verified sample-study load path immediately; the current browser study is not rebound until the load request has succeeded.
- Direct MR presentation now initializes the normalized MRI isovalue control to **0.35** when that value is inside the qualified descriptor range.
- The scientific/backend fallback remains `DEFAULT_MR_NORMALIZED_ISOVALUE = 0.50`; CT remains `DEFAULT_CT_BONE_ISOVALUE_HU = 300.0`.

The 0.35 value is therefore a browser presentation initialization, not a change to the normalized-signal algorithm or backend fallback contract.

## Safety boundaries

The existing `/api/sample-studies/{sample_id}/load` route, payload integrity checks, provenance handling, canonical-volume construction, and study activation semantics are reused unchanged. No MRI inference or production MRI label-map import is part of this step.

The historical D4.5D qualification-only delta guard is not replayed because it is intentionally bound to its historical base. Its backend invariants are checked through current focused regression contracts instead.

## Final manual acceptance

Manual acceptance completed successfully on the qualified Post-D6 implementation.

Verified:

- CT sample cards render the approved CT SVG artwork.
- MR sample cards render the approved MR SVG artwork.
- Sample actions use the concise `Open` label.
- The former `Replace the current workspace?` confirmation is absent.
- Selecting `Open` starts the existing verified sample-load workflow immediately.
- Direct MR initializes its presentation isovalue at `0.35`.
- The qualified backend Direct MR default remains `0.50`.
- Direct CT remains initialized at the existing `300 HU` baseline.
- MR -> CT -> MR transitions remain clean with no stale modality presentation.
- MRI inference was not run.
- No production MRI import was performed.

This remains a UI/presentation adjustment. The qualified Direct-MR backend,
Patient-LPS geometry, CT/HU behavior, segmentation contracts, and Phase 6J-D
scientific acceptance remain unchanged.
