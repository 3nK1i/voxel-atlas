# CT-B3A — Broader anatomical 3D palette for existing CT segmentations

Baseline: `6515d65e216c043c8a2ff6127c7193ff52ee2f24` on `phase6-accurate-surfaces`.

## Scope

- Extend the existing CT-B2 **3D-only** anatomical-color mapping using the pinned, recognized TotalSegmentator `total` canonical structure names and groups. Coordinate skeletal bone coloring for ribs, sternum, scapulae, clavicles, vertebrae, skull, pelvis and other known bones. Give `costal_cartilages` a separate subdued cartilage tone: it is not bone.
- Apply distinct illustrative surface colors to recognized lungs and other respiratory structures, abdominal organs, muscles, heart, arteries, veins and other known tissue labels. These are *illustrative display colors*, not radiological tissue characteristics, diagnostic labels, or clinical color standards.
- Leave unknown/unrecognized structure names and groups on their current scientific colors rather than infer anatomy from RGB or label ID. The palette only recolors structures represented in the active segmentation; it does not create anatomy outside CT scan coverage.
- Reuse CT-B1 material color overrides. Retain the original shared structure colors and per-structure opacity, MPR overlays, Patient-LPS geometry, surface-fidelity choices, segmentation data, clipping and the Scientific restoration path. No new segmentation or geometry requests on a palette switch.
- Only existing *visible* surfaces can be seen. Internal organs may be occluded by opaque exterior structures; use the existing Anatomical Structures Show/Hide, Iso and per-structure opacity controls to inspect them. This step does not automatically hide anatomy or make tissues transparent.
- Bump both the application module URL and anatomical-palette import URL to avoid stale browser modules after upgrade. The earlier CT-B2 test that required scientific organ/cartilage colors is updated because CT-B3A intentionally expands the preset; it still checks color isolation, reversible Scientific mode and unsupported-label fallback.

## Acceptance

Run `bash scripts/run_ct_b3a_checks.sh`, then review the existing locally segmented CT study in Surface mode. Compare Scientific → Anatomical → Scientific; check all available ribs, spine and shoulder bones; inspect a liver/heart/lung (if segmented) after isolating or hiding occluding structures. Keep identical MPR slice positions and confirm MPR overlay colors are unchanged. Check Surface → Combined → Surface, clipping and a second study if available. No new segmentation job is required for the color change. Record unavailable sample/structures as not tested; do not infer clinical accuracy from display colors.
