# VoxelAtlas

VoxelAtlas is a web-based medical imaging workspace under active development. V1 is centered on one end-to-end product flow: **DICOM data -> reconstruction -> interactive patient-specific 3D visualization**.

VoxelAtlas is currently an engineering/research application. It is not a certified diagnostic or medical-device product.

## Current status

The accepted foundation includes FastAPI authentication with Argon2id password verification, opaque server-side sessions, the responsive VoxelAtlas login UI, a deployed production service, the Phase 2B final V1 workspace shell, the Phase 3A DICOM study-ingestion foundation, the Phase 3A-R2 clinical viewer polish, and Phase 3B DICOM geometry/reconstruction-readiness qualification.

## Locked V1 workspace

The workspace is intentionally focused on medical imaging and anatomical inspection:

- final VoxelAtlas header with ergonomic light/dark mode
- 3-stage workflow: Data -> Reconstruction -> 3D Visualization
- real CT/MR DICOM folder upload and Study/Series metadata discovery
- geometric slice ordering, orientation/spacing validation, and reconstruction-readiness qualification
- study and reconstruction status panel
- large Three.js anatomy viewer
- Axial / Coronal / Sagittal MPR shell with truthful empty states until a DICOM volume exists
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

Phase 3A adds `pydicom` to the backend profile for metadata-only DICOM header parsing. The heavier medical-processing dependency inventory remains in `requirements/medical-processing.txt` for volume/reconstruction phases.

## Validation

Run the current compact regression from the repository root:

```bash
bash scripts/run_phase3b_checks.sh
```

## Locked V1 roadmap

1. foundation, login, authentication, and deployment
2. final V1 workspace target alignment
3. DICOM upload and study ingestion - Phase 3A complete; Phase 3B geometry qualification implemented
4. patient 3D volume construction and MPR
5. patient-specific anatomical reconstruction
6. end-to-end Full Volume / Skull / Brain / Skull + Brain visualization
7. UX, performance, and robustness
8. production security and V1 qualification

Post-V1 work includes atlas-region interaction, AR/XR, advanced planning workflows, PACS/DICOMweb, and additional anatomical atlases.

## Development policy

Development is performed on phase branches. `main` represents accepted validated states. Each implementation step is kept narrow and is closed only after automated checks, targeted manual validation, diff inspection, commit, and push.

Raw medical datasets, generated outputs, `.env`, and local virtual environments are intentionally excluded from Git.
