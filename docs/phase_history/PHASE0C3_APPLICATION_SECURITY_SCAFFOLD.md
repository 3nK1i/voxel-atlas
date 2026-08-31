# Phase 0C3 — Application/security scaffold and visual contract

## Scope

Phase 0C3 is the final foundation step before login implementation. It adds a standard-library backend configuration boundary, a backend dependency inventory, safe environment-variable examples, and preservation of the three supplied authoritative visual references.

No authentication route, login UI, dashboard UI, existing viewer, prototype, or medical-processing implementation is changed in this step.

## TDD sequence

The Phase 0C3 contract test was written first against the Phase 0C2 checkpoint. The initial targeted run failed because the backend configuration module, backend dependency manifest, visual-reference directory, environment example, runner, and documentation did not exist.

The narrow implementation then introduced those foundation artifacts and re-ran the targeted contract plus the complete Phase 0C2 regression.

## Exit criteria

- supplied `logo.png`, `login.png`, and `ui.png` hashes match the authoritative source assets;
- production configuration rejects missing/weak secrets and insecure cookies;
- real `.env` variants remain ignored while `.env.example` is trackable;
- the backend dependency inventory is explicit but does not claim unqualified pins;
- Phase 0C2 regression remains green;
- protected viewer/prototype files remain unchanged.
