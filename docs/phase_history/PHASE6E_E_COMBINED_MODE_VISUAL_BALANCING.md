# Phase 6E-E — Combined-mode visual balancing

Base: `fd74ea2161ea19388c7503be97b055d9d31c896a`

Phase 6E-E balances the existing Combined presentation without changing patient-space geometry, source data, reconstruction provenance, or the 300 HU Direct CT baseline. The user-controlled volume opacity remains authoritative state; Combined mode derives a temporary effective display opacity from it. Direct CT surface opacity is reduced only for Combined composition, while segmentation semantic colors and per-structure opacity remain authoritative and unscaled.

Fidelity and Presentation use explicit composition policies. Leaving Combined restores the exact user volume opacity and an opaque Direct CT surface. Mode/profile switching remains presentation-only and does not build, fetch, dispose, or mutate geometry.

6E-F performs final real-study qualification and Phase 6E closure. Phase 6F advanced structure interaction is not enabled here. Clinical validation is not claimed.
