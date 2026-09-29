# Phase 5C — Canonical Patient LPS label-map import

## Status

Phase 5C adds the provider-neutral boundary that turns a qualified segmentation
job output into an immutable VoxelAtlas label map. It does not render overlays,
generate surfaces, enable manual correction, or claim clinical validity.

## Import contract

Only a terminal `succeeded` job with `qualified_execution` output may be
imported. Before conversion, VoxelAtlas revalidates the immutable terminal job
seal, source study and series identities, canonical volume descriptor and
artifact hashes, model descriptor, task-definition fingerprint, provider-mask
hash, and present-label inventory.

The provider NIfTI is read only by an isolated worker in the qualified external
environment. The FastAPI environment continues to depend on NumPy but does not
import nibabel, torch, nnU-Net, or TotalSegmentator.

## Canonical geometry

The worker converts the NIfTI RAS affine back to DICOM Patient LPS by applying
`diag(-1,-1,1,1)`. It requires the mask grid to match the canonical source
shape and affine within a bounded numeric tolerance. Phase 5C deliberately
rejects a shifted, rotated, scaled, or reordered model grid instead of silently
resampling integer labels.

The stored descriptor preserves:

- canonical array order `[slice,row,column]`;
- canonical `uint16` labels;
- voxel-index-to-Patient-LPS affine in millimetres;
- original model-index-to-Patient-LPS affine;
- source-to-model and model-to-source index transforms;
- explicit `resampled=false` and `interpolation=none` provenance.

The initial TotalSegmentator baseline uses an unchanged voxel grid, so both
index transforms are identity matrices. Recording them explicitly prevents a
future provider from silently changing geometry.

## Durable artifacts

Canonical maps are stored below
`VOXELATLAS_DATA_DIR/segmentation/label-maps/map-<identity>/`. Each directory
contains `labels.npy` and `manifest.json`, both private and excluded from Git.
The identifier is derived from immutable job/source/model/mask provenance and
the canonical artifact SHA-256. Re-importing the same sealed job is idempotent.

Loading a descriptor rechecks its provenance fingerprint, deterministic
identity, canonical artifact hash, array shape/dtype/label inventory, live
source binding, and terminal job binding. Tampered or stale artifacts are never
reported as ready.

## Application boundary

Authenticated no-store endpoints expose safe descriptors only:

- `GET /api/segmentation/label-maps`
- `GET /api/segmentation/label-maps/{label_map_id}`

No filesystem path or raw patient artifact is returned. Phase 5D will add the
bounded label-data transport and synchronized colored MPR overlays.

## Operator flow

Import the already-qualified Phase 5B2 job using the isolated provider Python:

```bash
python scripts/import_phase5c_segmentation_label_map.py \
  --data-dir /var/lib/voxelatlas \
  --python /opt/voxelatlas-segmentation/bin/python \
  --job-id seg-0123456789abcdef0123456789abcdef \
  --confirm-nonclinical
```

The operation is local, performs no network access, does not rerun inference,
and retains the original NIfTI and job evidence.
