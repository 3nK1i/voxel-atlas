# Verified baseline handoff

The repository baseline was imported from the inspected handoff package:

- Archive: `medical_skull_3d_demo_handoff_20260831_112547.zip`
- SHA256: `9233614c70239d331ed9317c2482e5a0a698ddb6d836bab025d0d42277489214`
- Authoritative baseline Git commit: `4764b641e38b812d994ffa644dfdbbaa9f0227aa`

Before the first Git commit, the extracted handoff passed:

- `scripts/check_v2b3a_prototype.py`
- `scripts/check_v2b3b_prototype.py`
- Python AST parsing for all 23 packaged Python scripts
- Node.js syntax checking for the existing web viewer and both JavaScript prototypes
- raw-medical-data staging sanity
- Git diff whitespace sanity

## Preservation policy

`prototypes/v2b3a/` and `prototypes/v2b3b/` are historical engineering references. Phase 0C1 records their exact file fingerprints so later production work can reuse their proven behavior without silently rewriting the accepted prototype evidence.

`web/` is the current product baseline and is expected to evolve in later phases. It is therefore validated structurally rather than frozen by content hash.

The empty baseline `src/` and `tests/` directories were present in the handoff but were not part of the initial Git commit because Git does not track empty directories. Phase 0C1 begins tracking `tests/` with the baseline contract test.
