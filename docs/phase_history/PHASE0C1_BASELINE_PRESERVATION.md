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

## Contract evolution in Phase 2A

Phase 0C1 originally froze both prototype directories. Phase 2A later made an explicit product decision to retain the VA cranial-opening reference (`prototypes/v2b3a/`) and mark VB (`prototypes/v2b3b/`) as retired from the live tree. Phase 0 regression therefore continues to fingerprint VA while VB remains preserved in Git history and the original verified handoff archive.
