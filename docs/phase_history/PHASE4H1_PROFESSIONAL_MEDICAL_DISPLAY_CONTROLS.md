# Phase 4H1 - Professional medical display controls

Phase 4H1 refines the existing true patient-volume renderer without changing the canonical medical volume or its DICOM Patient LPS geometry.

## Delivered

- CT display window level and width operate in calibrated Hounsfield units.
- MR display window center and width operate in native relative intensity and are never labelled as HU.
- Windowing is independent from the advanced lower and upper intensity boundaries.
- Overall opacity remains an independent shader parameter and now sits beside Absorption inside progressive disclosure, avoiding an isolated control section without coupling their semantics.
- Any manual window, boundary, or absorption adjustment moves the preset selector to Custom while retaining the source preset as the reset baseline.
- Interactive, Balanced, High, and Maximum user policies select bounded settled targets.
- Every user policy still enters a lower-cost interactive profile during orbit, pan, zoom, clipping, transfer, opacity, and auto-rotation activity, including measured frame-pressure backoff.
- Advanced controls use progressive disclosure to keep the right panel compact.
- The upload and Full Volume actions share a restrained medical-blue visual language, while the workflow uses the same blue state language instead of green.
- The reconstruction card uses explicit voxel-volume and readiness SVG icons.
- Existing shared-crosshair and MPR window-reset tools have clearer labels and visible acknowledgement; each Axial, Coronal, and Sagittal panel can enter native browser fullscreen independently.
- Small workspace typography is selectively enlarged with responsive bounds rather than globally scaling the interface.

## Medical and architectural boundaries

Windowing, transfer mapping, opacity, absorption, and sampling are display parameters only. RG8 samples continue to decode into the original CT HU or MR intensity domain before display mapping. No canonical voxel value is rewritten, no MPR geometry is changed, and no surface, segmentation, projection mode, shading model, or dual-sided clipping is introduced.

Phase 4H2 can add opacity softness, gradient-based Edge Definition, and shading on this display-control foundation. Projection modes and six-plane clipping remain later isolated milestones.

## Validation

Run:

```bash
bash scripts/run_phase4h1_checks.sh
```

Manual validation must include at least one real CT and one real MR volume, every preset, Custom transition and reset, every quality policy, interaction-to-settled restoration, advanced-control disclosure, clipping regression, opacity regression, shared MPR center/reset actions, and fullscreen entry/exit for all three MPR planes before commit.
