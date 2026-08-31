# Development environment

Phase 0C2 defines the minimum environment contract without changing the workstation or installing packages automatically.

## Core development profile

The core profile is required for baseline development and validation:

```bash
python3 scripts/check_phase0c2_environment.py --profile core
```

It checks:

- Python 3.11 or newer. Ubuntu 24.04 / Python 3.12 is the current primary development target.
- Git availability.
- Node.js 20 or newer for JavaScript syntax validation.
- critical repository paths used by the preservation and dependency checks.

The checker **does not install**, upgrade, remove, or reconfigure software.

## Medical-processing profile

The existing DICOM/CT/mesh utility scripts currently import the packages listed in `requirements/medical-processing.txt`.

To explicitly qualify those optional processing dependencies in the active Python environment:

```bash
python3 scripts/check_phase0c2_environment.py --profile medical
```

The medical profile is not required to render the preserved browser baseline. It becomes a required gate when work reaches DICOM/study processing phases or when one of the existing processing scripts is intentionally used.

## Dependency locking policy

`requirements/medical-processing.txt` is an inventory in Phase 0C2, not yet a production lock file. Exact compatible versions will be qualified and pinned from a controlled project environment before medical-processing functionality becomes a production dependency.

This avoids claiming reproducibility from version pins that have not yet been exercised together on the target environment.

## Full current validation

Run:

```bash
bash scripts/run_phase0c2_checks.sh
```

This chains the Phase 0C1 preservation regression, the Phase 0C2 contract tests, and the core environment probe.

## Phase 1 backend profile

Phase 1B introduces executable FastAPI/Argon2id HTTP contracts. Before running Phase 1B validation, the active Python environment must provide the packages in `requirements/backend.txt` and `requirements/test.txt`.

Check without installing anything:

```bash
python3 scripts/check_phase1b_backend_environment.py
```

If dependencies are absent, use a controlled project Python environment before installation rather than modifying unrelated system/project environments.
