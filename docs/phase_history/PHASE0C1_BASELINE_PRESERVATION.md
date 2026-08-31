# Phase 0C1 — Baseline preservation contract

## Scope

Phase 0C1 adds repeatable baseline validation and project documentation without modifying the accepted viewer, prototypes, models, or medical-processing scripts.

## Added

- root project README
- verified handoff record
- immutable fingerprint check for both preserved prototype directories
- standard-library unit contract for baseline preservation
- single terminal validation runner

## Explicitly unchanged

- `web/`
- `prototypes/v2b3a/`
- `prototypes/v2b3b/`
- existing GLB assets
- existing DICOM/CT/mesh-processing utilities

## Exit criteria

Phase 0C1 is accepted only when:

- preserved prototype fingerprints match the verified handoff
- both legacy prototype smoke checks pass
- all packaged Python scripts parse successfully
- existing JavaScript files pass `node --check`
- the Phase 0C1 unit contract passes
- `git diff --check` is clean
- a minimal browser sanity check confirms the accepted baseline still loads
