# Phase 4H2-R1A - Volume Definition and Shading

## Scope

Phase 4H2-R1A refines the existing true patient-volume ray marcher with three display-only controls inside Advanced rendering:

- Opacity softness fades the selected intensity interval at its lower and upper boundaries.
- Edge definition uses the local voxel-intensity gradient to emphasize anatomical transitions without creating a surface or segmentation.
- Depth shading applies conservative gradient-based illumination for improved spatial perception.

Each CT and MR preset supplies bounded defaults. Manual changes enter the existing Custom state. Zero remains a valid value for every enhancement, allowing the original unenhanced rendering response. Maximum settings now produce deliberately distinct, bounded display responses so the complete control range remains useful.

The visible intensity minimum and maximum use one stable source-intensity scale and move independently. Only the actively moved boundary is constrained if it would cross the other boundary. Changing one handle therefore never rescales or moves the untouched handle.

R1A also guards transfer-control initialization and advances the application cache key. This prevents an undeclared legacy interval variable from disabling the renderer after a patient volume has loaded.

## Medical-data invariants

- The canonical float32 patient volume is authoritative and unchanged.
- The verified RG8 GPU texture is uploaded once and reused.
- All interaction updates shader uniforms only; it does not refetch, rebuild, or rewrite the volume.
- CT values remain HU and MR values remain relative modality intensity.
- MPR, Patient LPS geometry, clipping, sample provenance, and authentication behavior are unchanged.
- Edge definition is gradient opacity, not anatomical segmentation.
- Depth shading is a display cue, not additional medical information.
- Definition gradients are transformed into DICOM Patient LPS physical space before edge and lighting response.
- Gradient sampling is shared between Edge definition and Depth shading and skipped for negligible-opacity samples.

## Validation

Run:

```bash
bash scripts/run_phase4h2_checks.sh
```

Manual qualification should cover one CT and one MR sample, preset reset, independent intensity-boundary movement, all three new controls at minimum/default/maximum using an unchanged camera view, camera interaction, responsiveness, and confirmation that MPR remains unchanged.
