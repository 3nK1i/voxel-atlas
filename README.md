# VoxelAtlas

VoxelAtlas is a web-based medical imaging workspace under active development. The V1 direction combines interactive 3D anatomy, synchronized multiplanar imaging, selective anatomical layers, and atlas-based exploration in a clean responsive interface.

## Current status

This repository currently contains the verified pre-V1 skull visualization baseline and preserved interaction prototypes. The baseline is intentionally kept intact while the production application is hardened in small validated phases.

VoxelAtlas is an engineering/research application at this stage. It is not a certified diagnostic or medical-device product.

## Preserved baseline

The verified handoff includes:

- `web/` — existing standalone skull viewer.
- `prototypes/v2b3a/` — preserved cranial-opening prototype.
- `prototypes/v2b3b/` — preserved Three.js directional-sectioning prototype.
- `scripts/` — existing DICOM, CT, mesh-building, inspection, and prototype validation utilities.

The two prototype directories are preservation references and must not be modified casually. Their exact Phase 0C1 fingerprints are checked automatically.

## Validation and environment

From the repository root, run the current full validation check:

```bash
bash scripts/run_phase1a_checks.sh
```

This chains the complete Phase 0 foundation regression and the Phase 1A authentication-core contract/probe.

The existing DICOM/CT/mesh scripts have a separate dependency inventory in `requirements/medical-processing.txt`. Their active Python environment can be qualified explicitly with:

```bash
python3 scripts/check_phase0c2_environment.py --profile medical
```

The medical profile is intentionally not installed or required by the preserved browser baseline.

## Authoritative visual references

The supplied product assets are preserved in `design/reference/`. `logo.png` is the product logo; `login.png` and `ui.png` are the authoritative login/dashboard visual references. Their exact hashes and intended use are documented in `docs/design/VISUAL_REFERENCE_CONTRACT.md`.

## Backend foundation

Phase 0C3 establishes the standard-library configuration/security boundary in `backend/voxelatlas/` and an unpinned Phase 1 backend dependency inventory in `requirements/backend.txt`. Real secrets remain outside Git; `.env.example` contains names and safe development defaults only.

## Authentication implementation

Phase 1A establishes the framework-independent authentication core: paired external credential configuration, generic authentication failures, opaque server-side sessions, expiry, and logout invalidation. FastAPI routes, Argon2id wiring, secure cookies, and the visual login page remain staged follow-on steps. No plaintext or default login password is committed.

## V1 direction

The locked V1 sequence is:

1. baseline hardening and preservation
2. login and authentication
3. responsive dashboard shell
4. production Three.js viewer and directional sectioning
5. upload/study lifecycle and DICOM foundation
6. Axial/Coronal/Sagittal MPR
7. Skull/Brain anatomical layers
8. atlas-region interaction in 2D and 3D
9. integrated UX/performance polish
10. security, reliability, deployment hardening, and V1 qualification

## Development policy

Development is performed on phase branches. `main` represents accepted validated states. Each implementation step is kept narrow and is closed only after automated checks, a small targeted manual validation, diff inspection, commit, and push.

Raw medical datasets and generated outputs are intentionally excluded from Git.
