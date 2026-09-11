# Phase 6E-F — Final real-study qualification and Phase 6E closure

Authoritative base: `40937d706a7b54f3f23f882c9195ab5ed4992dc8` (`phase6-accurate-surfaces`, Phase 6E-E closed).

## Scope

Phase 6E-F is a **qualification-only closure step**. It does not redesign or modify the qualified rendering implementation from 6E-A through 6E-E. Production geometry, Patient LPS coordinates, topology, canonical patient volume, segmentation labels, semantic colors, per-structure opacity, Direct CT extraction, the locked **300 HU** default, Fidelity materials, Presentation lighting/material polish, Combined-mode balancing, visualization-mode semantics, explicit Build Surface behavior, and explicit segmentation-surface selection remain unchanged.

The purpose of 6E-F is to bind the final Phase 6E presentation to one real CT study and then perform the final manual visual matrix before Phase 6E is closed.

## Automated closure gate

Run:

```bash
export VOXELATLAS_SURFACE_PYTHON="$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python"
bash scripts/run_phase6e_f_checks.sh
```

This gate reruns the Phase 6E Fidelity/Presentation/Combined contracts, relevant Phase 6D2C mode/source regression, complete previous regression, syntax checks, patient-data Git safety, read-only qualifier safety, and an exact qualification-only delta guard. No production `backend/` or `web/` path may change in 6E-F.

Success ends with `PHASE6E_F_AUTOMATED_CHECKS_OK=YES`. Real-study execution and manual visual review remain separate gates.

## Real-study engineering qualification

Use the already-qualified real Head and Neck CT and its sealed canonical segmentation label map. At least one segmentation label must be supplied; label 91 (skull) is the primary presentation structure used in the previous Phase 6E manual work. Additional already-present labels may be repeated with `--label-id`.

Example:

```bash
python scripts/qualify_phase6e_f_real_study.py \
  --data-dir /home/eiatech/Desktop/voxel-atlas/data \
  --surface-python "$HOME/.local/share/voxelatlas/surface-runtime-phase6a/bin/python" \
  --label-map-id map-c2c950145b6f01686eb9fb4d870bf53f \
  --label-id 91
```

The qualifier validates that the active source is CT/HU, the canonical source volume remains immutable, Direct CT is derived at the locked 300 HU baseline in Patient LPS, the canonical segmentation label map belongs to the same study and remains immutable, and the requested segmentation presentation surface is the qualified refined Patient-LPS derivative. It does not make an aesthetic judgment and does not make a clinical claim.

Success ends with:

```text
PHASE6E_F_REAL_STUDY_QUALIFICATION_OK=YES
SOURCE_VOLUME=IMMUTABLE
SOURCE_LABEL_MAP=IMMUTABLE
GEOMETRY_CHAIN=PATIENT_LPS
DIRECT_CT_BASELINE=300_HU
CLINICAL_VALIDATION=NOT_CLAIMED
```

## Final manual presentation matrix

Using the same qualified real study and resident geometry, perform the following focused review. The browser Network panel should be cleared immediately before switch-only checks so qualification can distinguish presentation state changes from explicit geometry/segmentation operations.

1. **Fidelity / Surface / Direct CT** — neutral geometry-first rendering remains readable through frontal, lateral, superior, inferior and oblique views. Direct CT remains the same 300 HU geometry.
2. **Presentation / Surface / Direct CT** — view-relative key/fill/rim lighting and material polish improve anatomical readability without changing geometry. Recheck the difficult superior/inferior/oblique skull and cavity views corrected in 6E-D.
3. **Fidelity / Surface / Segmentation** — semantic colors and per-structure opacity remain authoritative; structure selection/highlight remains correct.
4. **Presentation / Surface / Segmentation** — semantic colors remain recognizable while the qualified Presentation shadow-lift/material treatment improves readability without recoloring labels.
5. **Fidelity / Combined** — patient volume + Direct CT + segmentation-derived surfaces coexist without one layer completely dominating the others.
6. **Presentation / Combined** — the same three layers remain readable with the stronger presentation composition, while anatomy, topology, Patient LPS alignment and semantic identity stay unchanged.
7. **Mode/profile round trip** — switch Volume → Surface → Combined → Volume and Fidelity → Presentation → Fidelity with resident geometry. No geometry build, segmentation start, marching-cubes request, or new surface fetch may be caused solely by these switches.
8. **User-opacity round trip** — set a distinctive non-default volume opacity, enter Combined, change profile, then return to Volume. The exact user opacity value must be preserved; Combined attenuation is presentation-only.
9. **Source selection** — toggle Direct CT and Segmentation selections while resident. Source selection must not become a visualization mode and must not silently rebuild geometry.
10. **Small backward sanity** — explicit Build Surface remains explicit, segmentation-surface selection remains explicit, only the active left-sidebar mode receives the active emphasis/check, and the known CT intensity-derived slab/FOV-like 300 HU geometry is not filtered away by unvalidated heuristics.

Browser console and server log must show no unexpected errors. Network activity generated by deliberate Build Surface, segmentation execution, or first-time segmentation-surface acquisition is not a failure; the switch-only portion must remain presentation/state-only.

## Closure rule

Phase 6E closes only when all three independent gates pass:

- `PHASE6E_F_AUTOMATED_CHECKS_OK=YES`;
- `PHASE6E_F_REAL_STUDY_QUALIFICATION_OK=YES`;
- the final manual presentation matrix is accepted on the real study.

Only after those gates pass should the 6E-F qualification-only delta be staged, reviewed, committed, and pushed.

Phase **6F** advanced structure interaction remains out of scope and is not enabled here. Phase **6G** quantitative surface-to-mask / MPR fidelity remains a later independent engineering qualification. Export remains deferred to Phase 7. Clinical validation is not claimed.
