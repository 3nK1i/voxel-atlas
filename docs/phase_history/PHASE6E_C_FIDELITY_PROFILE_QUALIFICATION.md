# Phase 6E-C — Fidelity profile qualification

Base: `51d276b903ada7eac904b9f73f17881673d45918`

Phase 6E-C qualifies **Fidelity** as the deterministic, neutral geometry-reference presentation for the existing Direct CT and segmentation-derived surface pipelines. It preserves the shared 6E-B Fidelity lighting/material values, semantic segmentation colors, structure opacity, the 300 HU Direct CT baseline, Patient LPS geometry, topology, and provenance.

The profile switch remains presentation-only: it updates shared light/material state in place and performs no surface build, geometry fetch, segmentation start, geometry disposal, patient-space transform, or source mutation. Surface and Combined mode semantics from Phase 6D2 remain unchanged.

A narrow reconstruction-card UI correction is included. Legacy `status-row[data-state="ready"]` styling had allowed the Volume card to retain a green-tinted readiness border while another reconstruction mode was active. All non-active ready Volume / Surface / Combined cards now use the same neutral card border/icon treatment; the selected mode alone receives active emphasis and the green check. This changes presentation only and does not change readiness or reconstruction state.

The stronger Presentation-profile anatomical readability and the deferred superior-skull / cavity lighting-material polish remain explicitly in **6E-D**. Phase 6F advanced interaction remains out of scope.

Clinical validation is not claimed.
