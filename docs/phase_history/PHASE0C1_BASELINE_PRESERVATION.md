# Phase 0C1 - Baseline preservation contract

## Original scope

Phase 0C1 added repeatable baseline validation and project documentation without changing the accepted handoff implementation.

## Contract evolution

The initial contract fingerprinted both packaged prototype lines. Later product decisions intentionally retired those prototypes from the live tree. Phase 2B completes that retirement and removes specialized demo-only utilities/assets that are outside the locked V1 workspace.

Historical evidence is not lost: the original verified handoff archive and Git history remain authoritative for retired source.

The active Phase 0 regression now verifies:

- retained skull GLB fingerprints from the original handoff
- original supplied visual-reference fingerprints
- intentional absence of retired prototype paths
- current JavaScript syntax
- Python AST validity
- raw-medical-data Git hygiene

This evolution prevents an obsolete prototype contract from blocking intentional product simplification while preserving reproducible evidence of the accepted baseline.
