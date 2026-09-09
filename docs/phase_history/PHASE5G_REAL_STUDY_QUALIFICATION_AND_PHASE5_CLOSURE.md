# Phase 5G — Real-study qualification and Phase 5 closure

Phase 5G closes the non-clinical segmentation engineering phase. It verifies that one
sealed canonical label map remains bound to its source CT study from provider output
through Patient-LPS MPR overlays, bounded preview surfaces, structure review, and the
manual-correction foundation.

## Closure contract

The real-study qualifier requires:

- one ready CT canonical label map with an immutable SHA-256 seal;
- exact study and label-map identity across overlay, surface, and quality services;
- nearest-neighbour label sampling in DICOM Patient LPS coordinates;
- valid RGBA evidence for axial, coronal, and sagittal center planes;
- a non-empty preview surface whose Patient-LPS bounds remain inside the acquired volume;
- a quality report tied to the same selected label;
- bounded metadata, overlay, and surface execution times;
- a deterministic inventory of comparable provider/model outputs for the same study.

Model candidates are inventoried, never ranked. Voxel count, visible-label count, or
surface size are not accuracy metrics. No clinical validation, diagnostic suitability,
or superiority claim is made.

## Ergonomic workspace closure

The Phase 5G UI refinement is intentionally presentation-only:

- the redundant `Anatomical Layers / Full Volume` sidebar card is removed while the
  verified patient-volume renderer and all medical transfer controls remain intact;
- multi-plane clipping typography is harmonized with the surrounding compact sidebar;
- the primary study action is consistently labeled `Upload DICOM` with its existing icon
  centered as one action;
- the persistent accessible theme control becomes an icon-only button in the account area,
  immediately before the authenticated user and logout action.

## Automated validation

Run from the repository root:

```bash
bash scripts/run_phase5g_checks.sh
```

The runner executes Phase 5G unit, architecture, UI, syntax, data-safety, dependency,
immutability, diff, and forward-compatible historical regression checks. Historical
assertions that specifically require the removed redundant layer card or the superseded
11 px clipping typography are enumerated by exact test ID; all remaining regression tests
must pass.

## Real-study qualification

The previously qualified Head and Neck CT study must be active before running:

```bash
python scripts/qualify_phase5f2_sample_study_identity.py \
  --data-dir /home/eiatech/Desktop/voxel-atlas/data \
  --sample-id head-neck-ct \
  --label-map-id map-c2c950145b6f01686eb9fb4d870bf53f

python scripts/qualify_phase5g_real_study.py \
  --data-dir /home/eiatech/Desktop/voxel-atlas/data \
  --label-map-id map-c2c950145b6f01686eb9fb4d870bf53f \
  --label-id 91 \
  --quality preview
```

Success ends with `PHASE5G_REAL_STUDY_QUALIFICATION_OK=YES`, while retaining
`MODEL_COMPARISON_RANKING=NOT_CLAIMED`, `SOURCE_LABEL_MAP=IMMUTABLE`, and
`CLINICAL_VALIDATION=NOT_CLAIMED`.

## Manual qualification

In the authenticated workspace, confirm:

1. the theme icon appears before the account identity and switches both themes;
2. the upload action is centered and always reads `Upload DICOM`;
3. no redundant Anatomical Layers / Full Volume card remains;
4. clipping labels align visually with adjacent structure and rendering controls;
5. Head and Neck CT still loads its 49 present structures, three synchronized overlays,
   one selected preview surface, correction-review controls, and the patient volume;
6. switching to Chest CT removes study-bound segmentation, and switching back restores it;
7. browser console and server access log show no unexpected error response.

Phase 6 may refine surfaces, render multiple selected structures simultaneously, and
materialize corrections under separately qualified immutable-output contracts.
