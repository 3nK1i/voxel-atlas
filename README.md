# VoxelAtlas

VoxelAtlas is a web-based medical imaging workspace under active development. V1 is centered on one end-to-end product flow: **DICOM data -> reconstruction -> interactive patient-specific 3D visualization**.

VoxelAtlas is currently an engineering/research application. It is not a certified diagnostic or medical-device product.

## Current status

The accepted foundation includes FastAPI authentication with Argon2id password verification, opaque server-side sessions, the responsive VoxelAtlas login UI, a deployed production service, the Phase 2B final V1 workspace shell, the Phase 3A DICOM study-ingestion foundation, the Phase 3A-R2 clinical viewer polish, Phase 3B DICOM geometry/reconstruction-readiness qualification, Phase 3C canonical patient-volume construction, and Phase 3D-R2.1 real synchronized MPR integration with final professional presentation, image-registered crosshairs, and harmonized clinical action/selection states. Phase 4A now defines the patient-specific anatomical reconstruction boundary, canonical patient-LPS mesh contract, provenance, stale-artifact protection, and authenticated reconstruction-status API. It does not yet claim a reconstructed patient skull or brain.

## Locked V1 workspace

The workspace is intentionally focused on medical imaging and anatomical inspection:

- final VoxelAtlas header with ergonomic light/dark mode
- 3-stage workflow: Data -> Reconstruction -> 3D Visualization
- real CT/MR DICOM folder upload and Study/Series metadata discovery
- geometric slice ordering, orientation/spacing validation, and reconstruction-readiness qualification
- canonical float32 patient-volume construction with explicit DICOM LPS coordinate provenance
- study and reconstruction status panel
- large Three.js anatomy viewer
- real Axial / Coronal / Sagittal patient-space MPR with synchronized crosshair, slice navigation, and window/level
- directional anatomical cut only: Axial, Coronal, Sagittal
- Clinical rendering only
- anatomy opacity with direct 0-100% semantics (100% fully opaque)
- synchronized anatomical orientation gizmo with transparent styling and axis arrows
- reset and auto-rotate actions
- layer architecture for **Full Volume**, **Skull**, **Brain**, and **Skull + Brain**

AR/XR, holographic rendering, visual-preset selectors, and specialized legacy cut behavior are outside the V1 workspace. Atlas-region exploration is post-V1.

The authoritative workspace target is `design/reference/workspace_v1_target.png`. The implementation target is approximately 95-100% visual fidelity while preserving real behavior, accessibility, responsiveness, and truthful feature states.

## Prototype retirement

Both original prototype lines are intentionally retired from the current tree. They remain recoverable from Git history and the verified original handoff archive. Phase 2B also removes the specialized demo-generation utilities and model artifact that existed only for the retired behavior.

## Runtime assets

Runtime web assets live under `web/assets/`. The qualified demo skull is `web/assets/models/skull_full.glb`.

Patient Full Volume, Brain, and Skull + Brain are later reconstruction outputs, not static placeholder models. See `web/assets/models/README.md`.

The product logo is served from `web/assets/logo.png`. Authoritative design references are stored under `design/reference/`.

## Development environment

Create/activate the project-local Python environment and install the declared backend/test profiles:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/backend.txt -r requirements/test.txt
```

Phase 3A adds `pydicom` for DICOM parsing. Phase 3C promotes `numpy` into the backend runtime profile because patient volumes are now decoded and persisted as float32 arrays. The remaining heavier reconstruction dependency inventory stays in `requirements/medical-processing.txt` until those later phases make it runtime-critical.

## Validation

Run the current compact regression from the repository root:

```bash
bash scripts/run_phase4a_checks.sh
```

## Locked V1 roadmap

1. foundation, login, authentication, and deployment
2. final V1 workspace target alignment
3. DICOM upload, study ingestion, geometry qualification, canonical patient volume, and real MPR - complete through Phase 3D
4. patient-specific anatomical reconstruction foundation and qualified Skull / Brain reconstruction
5. end-to-end patient-specific Full Volume / Skull / Brain / Skull + Brain visualization
6. UX, performance, and robustness
7. production security and V1 qualification

Post-V1 work includes atlas-region interaction, AR/XR, advanced planning workflows, PACS/DICOMweb, and additional anatomical atlases.

## Development policy

Development is performed on phase branches. `main` represents accepted validated states. Each implementation step is kept narrow and is closed only after automated checks, targeted manual validation, diff inspection, commit, and push.

Raw medical datasets, generated outputs, `.env`, and local virtual environments are intentionally excluded from Git.

### Phase 3D-R2 - Final Phase 3 presentation

Real axial, coronal and sagittal views are fitted by patient-space physical extent inside full black diagnostic fields, with synchronized crosshairs, orientation markers, physical position, slice index, and compact W/L controls. The temporary scale bracket is retired. The 3D viewer uses the final segmented six-button clinical toolbar with real rotate/pan modes and target-style active states. CT data remains CT; no MRI appearance is fabricated.

### Phase 3D-R2 final selection-state harmonization

The active anatomical layer now uses the same illuminated blue clinical selected state as Directional Cut and the 3D interaction toolbar. Unavailable patient layers remain disabled and truthful, while `aria-pressed` stays synchronized with the active layer. This is a presentation-only closure correction; the patient-space MPR computation and Phase 3 medical-data pipeline are unchanged.

### Phase 3D-R2.1 - Final crosshair and DICOM CTA polish

MPR crosshairs are registered in pixels to the exact contained patient-image rectangle, so crosshair lines stop at the displayed anatomy bounds instead of drifting through black letterbox margins. Pointer mapping continues to use the displayed canvas rectangle. The Upload/Replace DICOM primary action now uses the same premium blue clinical language as the selected Directional Cut and anatomy controls while remaining an action rather than a persistent selected mode.


### Phase 4A - Anatomical reconstruction foundation

Phase 4A introduces the reconstruction service boundary without generating anatomy yet. Future providers consume only the qualified canonical patient volume and must publish triangle meshes directly in DICOM patient LPS millimetres. CT HU is qualified as the first skull source, while MR is the first V1-qualified brain source. Published anatomy is tied to the exact source-volume descriptor and becomes stale automatically if that source changes. Private mesh paths and provider parameters are not exposed by the reconstruction-status API.
