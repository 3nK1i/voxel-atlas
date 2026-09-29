# Phase 6J-F — Final integrated MRI acceptance and closure

Authoritative qualification base: `6bbbef3` on `phase6-accurate-surfaces`.

## Scope

Phase 6J-F closes the MRI extension after the qualified Phase 6J-D implementation,
Phase 6J-E robustness qualification, and final real-study end-to-end acceptance.

This closure does not introduce new production behavior.

## Existing-study acceptance

The previously qualified MRI study was restored successfully with:

- canonical patient volume and synchronized MPR;
- persisted MRI segmentation rediscovery without re-execution;
- source-bound MPR overlays;
- semantic Brain / Spinal Cord surfaces;
- Direct MR normalized-signal presentation;
- browser presentation initialization at 0.35;
- Direct MR and semantic surface coexistence.

Direct CT backward compatibility remained intact at the established 300 HU baseline
with CT-only region evidence.

## New-study final acceptance

A distinct real MRI DICOM study was uploaded through the normal application workflow.

The final integrated acceptance verified:

- MRI study recognition and canonical patient-volume construction;
- synchronized Patient-LPS MPR;
- Direct MR availability before semantic segmentation;
- normalized-signal Direct MR presentation with 0.35 browser initialization;
- absence of CT/HU-only controls for MRI;
- one intentional TotalSegmentator `total_mr` inference;
- one successful canonical MRI label-map import;
- persisted MRI overlay and semantic 3D surfaces;
- Direct MR plus semantic-surface coexistence in Surface and Combined modes;
- browser refresh/restart rediscovery without a second MRI inference;
- MRI -> CT -> MRI isolation with no stale cross-modality presentation.

## Persistence and provenance

The final real-study acceptance preserved the existing study/source binding,
immutable-source checks, canonical label-map persistence, Patient-LPS geometry,
and stale asynchronous completion protection.

No second MRI inference was run after persistence was established.

## Locked modality semantics

- Direct MR remains non-semantic normalized-signal geometry.
- Browser Direct MR presentation initializes at 0.35.
- Backend Direct MR scientific fallback remains 0.50.
- Direct CT remains native HU with the established 300 HU baseline.
- CT region evidence remains CT-only.
- Semantic MRI surfaces remain segmentation-derived.
- Patient-LPS remains the canonical presentation coordinate system.

## Safety boundary

- Final MRI inference: run once on the newly uploaded acceptance study.
- Production MRI import: run once for the resulting qualified output.
- Second MRI inference after persistence/reload: not run.
- Clinical validation: not claimed.

## Closure

Phase 6J MRI implementation, lifecycle robustness, persistence, provenance,
cross-modality isolation, CT compatibility, and final real-study acceptance are
qualified for integration into `main`.
