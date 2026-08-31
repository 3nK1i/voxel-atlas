# VoxelAtlas

VoxelAtlas is a web-based medical imaging workspace under active development. The V1 direction combines authenticated 3D anatomical exploration, synchronized multiplanar imaging, and selective anatomical layers in a clean responsive interface.

VoxelAtlas is currently an engineering/research application. It is not a certified diagnostic or medical-device product.

## Current status

The accepted foundation includes real FastAPI authentication with Argon2id password verification, opaque server-side sessions, and the responsive VoxelAtlas login UI. Phase 2 migrates the production workspace to the retained VA cranial-opening lineage.

## Workspace direction

The production workspace is intentionally focused on clinical anatomy rather than presentation presets:

- Three.js interactive 3D viewer
- VA continuous cranial-opening control
- directional sectioning: Up / Down, Front / Back, Left / Right
- Clinical rendering only
- skull opacity
- reset and auto-rotate actions
- anatomical-layer architecture for **Skull**, **Brain**, and **Skull + Brain**

AR/XR, holographic rendering, and visual-preset selectors are outside the V1 workspace. Atlas-region exploration is deferred to **post-V1**.

## Preserved and retired prototypes

- `prototypes/v2b3a/` — preserved VA cranial-opening engineering reference.
- `prototypes/v2b3b/` — intentionally retired from the current tree in Phase 2A; still recoverable from Git history and the verified handoff archive.

The VA reference remains fingerprinted by the Phase 0 regression and must not be modified casually.

## Runtime assets

Runtime web assets live under `web/assets/`. The qualified skull is `web/assets/models/skull_full.glb`.

The reserved V1 brain-layer path is:

```text
web/assets/models/brain.glb
```

A brain mesh is never fabricated by the browser. Brain and Skull + Brain remain disabled until a real co-registered `brain.glb` is supplied. See `web/assets/models/README.md`.

The product logo is served from `web/assets/logo.png`. Authoritative design references remain immutable under `design/reference/`.

## Development environment

Create/activate the project-local Python environment and install the declared backend/test profiles:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/backend.txt -r requirements/test.txt
```

The separate medical-processing dependency inventory is in `requirements/medical-processing.txt` and is qualified only when DICOM/processing work requires it.

## Validation

Run the current workspace regression from the repository root:

```bash
bash scripts/run_phase2a_checks.sh
```

## V1 roadmap

1. baseline hardening and preservation
2. login and authentication
3. authoritative responsive 3D workspace
4. upload/study lifecycle and DICOM foundation
5. Axial / Coronal / Sagittal MPR
6. Skull / Brain / Skull + Brain anatomical layers
7. integrated UX/performance polish
8. security, reliability, deployment hardening, and V1 qualification

Post-V1 work includes atlas-region interaction, AR/XR, advanced surgical-planning workflows, PACS/DICOMweb, and additional anatomical atlases.

## Development policy

Development is performed on phase branches. `main` represents accepted validated states. Each implementation step is kept narrow and is closed only after automated checks, a small targeted manual validation, diff inspection, commit, and push.

Raw medical datasets, generated outputs, `.env`, and local virtual environments are intentionally excluded from Git.
