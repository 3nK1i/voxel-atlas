# Phase 0C2 — Runtime and dependency foundation

## Scope

Phase 0C2 establishes a repeatable environment/dependency contract for the verified pre-V1 baseline. It does not redesign the UI, alter the preserved viewers, install packages, or begin authentication work.

## TDD evidence

The Phase 0C2 contract tests were authored before the implementation artifacts. The initial red run failed because the environment checker, requirements inventory, current runner, and environment documentation did not yet exist. The narrow implementation then satisfied that contract.

## Added

- `requirements/medical-processing.txt` — explicit inventory of third-party packages already imported by the existing medical-processing scripts.
- `scripts/check_phase0c2_environment.py` — non-mutating core/medical environment probe.
- `scripts/run_phase0c2_checks.sh` — current full validation entry point, including Phase 0C1 regression.
- `tests/test_phase0c2_environment_contract.py` — Phase 0C2 environment/dependency contract.
- `docs/development/ENVIRONMENT.md` — environment usage and locking policy.

## Modified

- `README.md` — points developers to the current full validation entry point and the optional medical environment qualification command.

## Non-goals

- no package installation
- no exact dependency pinning before compatibility qualification
- no FastAPI/authentication dependencies yet
- no changes to `web/` or preserved prototypes
- no DICOM pipeline redesign

## Exit criteria

- Phase 0C1 regression remains green.
- Phase 0C2 unit contract is green.
- core environment probe passes on the development workstation.
- compile/shell/diff checks pass.
- no preserved viewer/prototype file changes.
