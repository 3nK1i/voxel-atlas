# Phase 3A-R1 - Clinical Viewer Rendering Polish

This narrow polish step follows the accepted Phase 3A DICOM study-ingestion foundation and intentionally does not change the DICOM ingestion, storage, Study/Series metadata, authentication, or reconstruction contracts.

## Scope

- restore a truly solid clinical default skull render
- keep opacity semantics direct: 100% means fully opaque, lower values progressively reveal transparency
- avoid accidental near-opaque transparency on initial load
- render both face orientations for the current demo mesh so inconsistent winding does not present as missing/translucent surface patches
- keep depth testing/writing enabled and use single-pass transparent rendering when opacity is reduced
- reduce initial skull screen size by about 15% by increasing the initial camera distance by 18%
- replace the small static orientation marker with a larger target-style anatomical orientation gizmo
- synchronize the gizmo with both OrbitControls camera orientation and the anatomy group rotation used by auto-rotate

## Anatomical gizmo convention

The current demo workspace uses Y for superior/inferior, Z for anterior/posterior, and X for right/left. The visible target-style labels are S, A, R, and L.

## Non-goals

This step does not repair or remesh the demo skull GLB, create patient-specific anatomy, populate MPR, or perform DICOM geometry validation. Those remain separate reconstruction/data phases.

## Acceptance

The automated contract requires:

- default opacity 100%
- direct slider-to-material opacity mapping, never inverted
- solid material defaults with depth test/write enabled
- approximately 15% smaller initial framing
- a synchronized S/A/R/L orientation gizmo
- unchanged Phase 3A regression behavior
