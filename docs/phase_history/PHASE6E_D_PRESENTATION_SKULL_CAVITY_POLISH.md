# Phase 6E-D — Presentation profile + skull/cavity lighting/material polish

Authoritative base: `df6ceecc18242b22c8490d4b4fad5c096a2f86cf` (`phase6-accurate-surfaces`).

Phase 6E-D keeps the qualified **Fidelity** profile unchanged and narrows all visual polish to **Presentation**. The Presentation rig now uses view-relative key/fill/rim directions so surface readability follows the camera through frontal, lateral, superior, inferior and oblique inspection instead of depending on one fixed world-light orientation. A brighter hemisphere ground contribution and restrained material shadow lift reduce excessively dark skull/cavity regions without modifying patient geometry.

Direct CT keeps the Phase 6D1 editable **300 HU** baseline and receives presentation-only warm bone material tuning. Segmentation surfaces retain their semantic structure colors and per-structure opacity; a small same-color emissive contribution lifts deep shadows without recoloring labels.

Profile changes update only resident lights/materials. They do not build, fetch, dispose, smooth, decimate, repair or otherwise mutate meshes; they do not change topology, Patient LPS coordinates, segmentation labels, source volumes, HU thresholds or provenance. Returning to Fidelity restores the locked 6E-C neutral reference.

Phase 6E-E combined-mode visual balancing remains separate. Phase 6F advanced structure interaction remains out of scope. Clinical validation is not claimed.
