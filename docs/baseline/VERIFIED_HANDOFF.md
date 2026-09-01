# Verified baseline handoff

The repository baseline was imported from the inspected handoff package:

- Archive: `medical_skull_3d_demo_handoff_20260831_112547.zip`
- SHA256: `9233614c70239d331ed9317c2482e5a0a698ddb6d836bab025d0d42277489214`
- Authoritative baseline Git commit: `4764b641e38b812d994ffa644dfdbbaa9f0227aa`

Before the first Git commit, the extracted handoff passed its packaged prototype, Python AST, JavaScript syntax, raw-medical-data, and diff-sanity checks.

## Preservation policy

The original handoff remains the immutable evidence source for historical prototypes and retired experimental utilities. The current tree is intentionally allowed to evolve as product direction becomes locked.

Phase 2B retires both historical prototype directories and the specialized demo-only utilities/assets that no longer belong to the V1 product. Their removal is intentional; they remain recoverable from Git history and the verified handoff archive.

The baseline regression now fingerprints the retained qualified skull assets and the original supplied design references while also asserting that retired prototype paths do not silently return.

`web/` is the current product implementation and is validated structurally rather than frozen by content hash.
