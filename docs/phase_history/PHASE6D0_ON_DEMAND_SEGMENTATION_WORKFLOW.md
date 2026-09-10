# Phase 6D0 — On-demand segmentation workflow

## Scope

Phase 6D0 removes semantic segmentation from the initial visualization critical path while preserving the existing Phase 5 provider-neutral segmentation, TotalSegmentator execution, canonical Patient-LPS label-map import, and Phase 6 surface pipelines.

The locked user workflow is:

1. Open or upload a DICOM study.
2. Make the canonical patient volume, synchronized MPR, and direct 3D volume rendering usable first.
3. Keep semantic segmentation inactive until an explicit user action.
4. When the user chooses **Start Segmentation**, reuse a valid existing segmentation for the same study when available; otherwise start the qualified CT TotalSegmentator job.
5. Present provider-reported progress, cancellation, failure, retry, and finalization states without fake percentages.
6. Import successful provider output through the immutable Phase 5C canonical Patient-LPS label-map path.
7. Activate segmentation overlay, structure controls, and segmentation-derived surfaces only after the result is explicitly requested and available.

This is a continuation of the existing architecture, not a replacement segmentation subsystem.

## Initial-load contract

`ensureMprReady()` no longer fetches a segmentation overlay descriptor. Both canonical-volume creation and already-ready volume restoration finish MPR and direct volume-rendering foundation setup before starting a non-blocking segmentation workflow status request. An existing label map is not automatically activated into MPR/3D presentation.

This makes semantic segmentation optional derived work instead of a prerequisite for initial patient-volume visualization.

## Explicit workflow states

The workflow exposes provider-neutral state derived from the existing job lifecycle:

- `idle`
- `queued`
- `starting`
- `running`
- `cancelling`
- `finalizing`
- `output_ready`
- `available`
- `failed`
- `cancelled`
- `unsupported`
- `unavailable`

The browser displays the backend/provider progress value. It does not synthesize elapsed-time percentages.

## Existing-result reuse

A canonical label map already bound to the current study is reusable after explicit user action. Reuse does not create or run another segmentation job. Cross-study label-map reuse remains forbidden by the existing source-study binding validation.

## New CT segmentation

The application wires the already-qualified Phase 5B2 `TotalSegmentatorProvider` only when `VOXELATLAS_SEGMENTATION_PYTHON` is explicitly configured. Execution remains subprocess isolated and uses the existing Phase 5B2 bridge script. The provider-neutral job service retains GPU selection, progress, cancellation, terminal provenance, and failure handling.

After a successful provider job, Phase 6D0 invokes the existing Phase 5C isolated import worker to create/reuse the immutable canonical Patient-LPS label map. The source volume and source provider mask are not modified.

`VOXELATLAS_SEGMENTATION_PYTHON` is intentionally independent from `VOXELATLAS_SURFACE_PYTHON`.

## Modality boundary

Phase 6D0 enables the already-qualified TotalSegmentator `total` task for CT only. It does not silently send MR data to a CT-only model. The UI explicitly states that the MRI segmentation provider is deferred to Phase 7.

## HTTP/UI contract

Authenticated, non-cacheable workflow endpoints are provided for status, explicit start/use, and cancellation. Provider execution runs after the start response through the application background-task boundary so the request itself does not block for the full model runtime. The browser polls only while a workflow explicitly started by the user remains active.

Study switching clears active workflow polling and segmentation presentation context, preserving cross-study isolation.

## Preserved contracts

Phase 6D0 does not modify:

- Phase 6A accurate Patient-LPS surface extraction;
- Phase 6B topology repair/refinement geometry;
- Phase 6C multi-structure surface presentation semantics;
- direct patient-volume ray marching;
- canonical source volumes;
- canonical source label maps;
- TotalSegmentator weights;
- patient data.

No clinical or diagnostic validation claim is introduced.

## Deferred roadmap boundaries

Phase 6D0 does not implement Phase 6D1 volume-derived isosurfaces, Phase 6D2 independent Volume/Surface/Combined controls, Phase 6E fidelity/presentation profiles or deferred lighting polish, Phase 6F advanced multi-structure interaction, Phase 6G fidelity metrics, or Phase 6H export.
