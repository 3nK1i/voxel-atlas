# Phase 6F-F — Final real-study interaction qualification and Phase 6F closure

Phase 6F-F is a **qualification-only** closure step for the interaction stack delivered across Phase 6F-A through Phase 6F-E. It does not add or redesign production rendering behavior.

## Scope

The step qualifies, together on the canonical real CT study, all interaction behavior introduced during Phase 6F:

- **Show / Hide / Isolate / Restore** and authoritative base visibility;
- exact per-structure opacity, including a representative **42%** round-trip;
- per-structure **Follow Directional Cut** participation;
- bounded anatomical-group **Explode anatomy** presentation;
- Fidelity and **Presentation** profile round-trips;
- **Surface** and **Combined** mode round-trips;
- refined surface presentation with explicit **accurate fallback** when the bounded refinement policy safely refuses;
- synchronized canonical **MPR** presentation that remains un-exploded;
- preservation of resident geometry, source volume, source label map, Patient LPS provenance, semantic colors and prior interaction state.

## Automated closure gate

The automated gate is intentionally qualification-only. It re-runs the focused Phase 6F-E/D/C/B/A checks, the Phase 6B refined-to-accurate fallback regression, the Phase 6E-F closure contracts, and the complete previous automated regression. The candidate itself is limited to documentation, tests and qualification scripts; no production rendering, worker, backend, geometry or browser presentation source is modified by Phase 6F-F.

The real-study source gate delegates to the already-qualified read-only Phase 6E-F real-study source qualifier. It must reconfirm CT/HU source provenance, 300 HU Direct CT reference, Patient LPS geometry chain and immutable source volume/label map before Phase 6F can close.

## Manual real-study interaction matrix

Run the following matrix on the same qualified real CT study after the automated gate and real-study source gate pass.

1. **Baseline state** — use Direct CT plus at least three segmentation surfaces from multiple anatomical groups. Confirm canonical alignment at `Explode anatomy = 0 mm` in Surface and Combined modes.
2. **Visibility/isolation** — exercise Show / Hide / Isolate / Restore, including isolating a structure whose base visibility is OFF. Restore must recover the exact previous visibility state and must not request new geometry.
3. **Opacity** — set a selected structure to **42%**. Round-trip Fidelity → Presentation → Fidelity and Surface → Combined → Surface. The structure must remain at 42% and preserve semantic color.
4. **Directional Cut participation** — make one cut intersect the selected structure. With **Follow Directional Cut** ON the structure follows the cut; OFF restores the whole resident structure while Direct CT and participating structures remain clipped; ON again restores the same cut.
5. **Exploded presentation** — test `0 → 20 → 40 → 0 mm`. Structures in the same anatomical group must travel together, different groups must separate, and returning to 0 mm must restore exact canonical alignment.
6. **Combined interaction preservation** — set opacity to 42%, Follow Directional Cut OFF and Explode anatomy to 25 mm; then run Iso → Restore, Fidelity → Presentation → Fidelity and Surface → Combined → Surface. All three interaction choices must survive the round-trip.
7. **Directional Cut + explosion coexistence** — with Follow Directional Cut ON and explosion at 25–40 mm, the cut must continue to remove the same anatomical portion of the exploded structure because the display clipping plane follows the display offset.
8. **MPR invariance** — MPR overlays stay in canonical Patient LPS and do not explode when 3D surfaces are exploded.
9. **Fallback presentation** — load/show the real-study segmentation surface set and confirm any bounded refinement refusal is reported explicitly as **accurate fallback**, not as a failed or silently refined surface.
10. **Network/geometry preservation** — clear the browser network panel, then change only visibility, isolation, opacity, clipping participation and explosion state. Already-resident presentation changes must cause **no geometry request** to segmentation-surface or volume-surface endpoints.
11. **Reset sanity** — Reset must return the interaction presentation to its documented defaults without modifying source data or provenance.

Phase 6F closes only after the automated gate, real-study source gate and this manual matrix all pass.

## Known deferred Direct CT issue

The previously observed Direct CT **300-HU slab/occlusion** component is deliberately not changed in Phase 6F-F. The all-clipping-off/full-range checks showed no evidence that Phase 6F interaction state destroyed Direct CT geometry. Investigation and any principled Direct CT surface-quality correction are deferred until **after Phase 6F closure**, before deeper Phase 6G quantitative/fidelity work.

This deferred item is not permission to apply arbitrary connected-component filtering or destructive cleanup. It must be investigated separately with source/provenance and geometry safety preserved.

## Safety and phase boundary

- Phase 6F-F is qualification-only.
- No production renderer, geometry, worker, backend, Patient LPS transform or source data is changed.
- No segmentation execution is triggered by the closure scripts themselves.
- No Phase 6G quantitative surface-to-mask fidelity claim is made here.
- This is **not clinical validation** and no regulatory/diagnostic claim is made.
