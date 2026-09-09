# Phase 5E - Anatomical Structure Panel

## Status

Implemented on `phase5-segmentation` from the accepted Phase 5D base
`c58b8ef2b235c787d05848fd66228d8312ee20bf`.

Phase 5E adds presentation controls for structures already present in the
immutable canonical Patient-LPS label map. It does not run inference, edit the
source labels, generate a 3D surface, or claim clinical validation.

## Structure catalog

The overlay descriptor now carries a provider-neutral catalog containing only
labels present in the selected map. Each entry includes a numeric label, stable
machine name, human-readable name, anatomical group, default visibility,
default opacity, and stable Phase 5D color.

The qualified `totalsegmentator/total` binding contains its complete public
117-label taxonomy from `totalsegmentator/map_to_binary.py`. The application
environment keeps a lightweight pinned copy and does not import
TotalSegmentator, nnU-Net, PyTorch, or NIfTI libraries. Unknown providers retain
safe `Label N` names in an explicit Other group instead of being mislabeled.

## Browser interaction

The right-side panel provides:

- text search by display name, provider name, anatomical group, or label number;
- compact expandable anatomical groups;
- show all, hide all, and deterministic reset;
- per-structure show/hide and one-click isolation;
- named row selection;
- selected-structure color and opacity controls.

Phase 5D RGBA pixels remain the authenticated, no-store transport contract. The
browser verifies their colors against the descriptor palette once, decodes a
local label-id buffer for each accepted MPR plane, and recomposites locally when
presentation controls change. Search and presentation updates do not request a
new grayscale MPR image or mutate any patient artifact. Crosshair navigation,
window/level, physical aspect, orientation, clipping, fullscreen, and volume
rendering remain unchanged.

## Safety boundaries

- The structure catalog remains bound to the current study and exact label map.
- Background label zero remains transparent and is never exposed as anatomy.
- Only labels present in the canonical map appear in the panel.
- Browser presentation state is ephemeral and cannot overwrite label data.
- Phase 5F1 owns segmentation-derived 3D surfaces.
- Clinical validation remains not claimed.

## Validation

Run:

```bash
bash scripts/run_phase5e_checks.sh
```

Then open the qualified Head and Neck CT and verify that search, grouping,
visibility, isolation, selection, color, opacity, reset, slice navigation, and
fullscreen presentation remain synchronized in axial, coronal, and sagittal
MPR. This is a non-clinical engineering visualization qualification.
