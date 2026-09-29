# Phase 6J-D5B — Study transition and stale-async lifecycle isolation

## Scope

D5B hardens browser-side study lifecycle ownership after the qualified MRI 3D and Direct-MR work. It does not change CT/MR scientific reconstruction, MRI normalization, segmentation inference, label-map geometry, or Patient-LPS contracts.

## Problem addressed

The surface layers already reject stale mesh completions with request generations and abort controllers, and normal study activation clears resident patient rendering. Several higher-level descriptor/build promises, however, were shared at module scope. A delayed completion from an earlier study, series, or canonical-volume revision could therefore temporarily own a promise or attempt a stale UI update after a study transition.

## D5B contract

A change in study id, reconstruction series, or canonical-volume revision now advances a browser study-lifecycle generation before the new study is bound. The transition detaches pending MPR, segmentation-overlay, segmentation-surface, Direct-volume descriptor, canonical-volume build, and automatic-surface intent ownership.

Async MPR, Direct-volume descriptor, segmentation overlay/surface descriptor, canonical-volume construction, ready-volume restoration, initial latest-study restoration, and volume-rendering preparation capture the active lifecycle and refuse stale completion. Promise finalizers clear shared ownership only when they still own the current promise.

Resident Direct and segmentation-derived mesh layers retain their existing generation/abort protections. `setMprVolumeState()` continues to clear old patient-scoped resident presentation when a study is applied. Workspace Reset remains presentation-only and does not destroy valid resident geometry.

## Preserved boundaries

- Direct MR remains normalized-signal, non-semantic visualization.
- Direct CT remains HU-based with the 300 HU baseline and CT-only region evidence.
- Patient-LPS remains unchanged.
- Existing persisted segmentation results are not deleted.
- Study switching does not start MRI segmentation.
- No MRI inference is run by D5B.
- Clinical validation is not claimed.

## Legacy regression compatibility

The Phase 6I-B1 automatic-surface regression previously asserted the older study-id-only stale-response guard. D5B intentionally strengthens that same guard with the study-lifecycle generation while retaining the study-id check. The legacy test is updated to assert the stronger generation-plus-study binding; production behavior is not weakened to satisfy the older assertion.

The Phase 6D2D mode-card regression also carried a CT-only literal ("Select to prepare Direct CT") from before Direct MR shared the volume-derived presentation path. The production UI is now intentionally modality-aware through `directVolumeSurfaceLabel()`. The legacy regression is updated to assert that modality-aware helper and its presentation template instead of forcing CT-only wording.

## Acceptance

D5B requires focused lifecycle tests, browser static checks, previous reset/mode regressions, D4.5C Direct-MR/CT regressions, D4 semantic-MRI regressions, syntax checks, and a clean whitespace diff before manual study-switch acceptance.
