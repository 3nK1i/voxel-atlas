# Phase 6B refined-surface accurate fallback correction

## Scope

This narrow compatibility correction is applied after Phase 6F-B closure and before Phase 6F-C. It does not change the Phase 6B refinement worker, topology policy, segmentation masks, Patient-LPS geometry, or surface extraction algorithms.

The browser continues to request the qualified `refined` presentation surface first. If and only if that request returns HTTP 422, and the descriptor's default surface quality is `accurate`, the browser performs one explicit fallback request for the canonical Phase 6A `accurate` surface.

## Safety behavior

- Refined remains the preferred presentation quality.
- The bounded Phase 6B topology/refinement policy is unchanged and is never relaxed.
- Non-422 refined failures do not trigger fallback.
- The accurate response must pass the existing media type, binding, SHA256, schema, provenance, label-map, label-id, and extraction validation before it is accepted.
- Fallback is visible in surface status and mesh metadata as `accurate fallback`; it is not reported as refined.
- A successful accurate fallback is not counted as a failed structure.
- If the accurate fallback also fails, the structure remains failed exactly as before.
- Source label maps remain immutable and no Patient-LPS vertices are altered by this compatibility behavior.

## Motivation

A qualified real-study edge case exposed a structure whose canonical mask and accurate surface were valid, while the conservative refined worker safely refused the derivative because the accurate reference topology could not be repaired within the bounded local face-only policy. The appropriate presentation behavior is therefore to preserve the safety refusal while continuing to display the already-qualified accurate surface with explicit provenance.

## Roadmap boundary

This correction does not enable Phase 6F-C transparency qualification, Phase 6F-D per-structure clipping, Phase 6F-E exploded presentation, or Phase 6F-F closure. It is a compatibility/safety correction only.
