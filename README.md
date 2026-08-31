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

## Baseline validation

From the repository root:

```bash
bash scripts/run_phase0c1_checks.sh
```

The check covers the preserved prototype fingerprints, existing prototype smoke contracts, Python syntax, JavaScript syntax, critical web assets, and the Phase 0C1 unit contract.

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
