# Phase 5B2 — TotalSegmentator execution qualification

## Status

Phase 5B2 implements the first real, bounded TotalSegmentator execution path for
VoxelAtlas. It remains an engineering/research qualification. It does not claim
clinical validity and does not expose segmentation in the web UI.

## Locked baseline

- provider: TotalSegmentator `2.18.0`
- task: `total`
- input modality: CT only
- task definition: 117 anatomical labels, fingerprint
  `2f9caff9c6fc38df9a134d8258835f30cd33651da5a9d8b5dab77fbc7dac2d67`
- output: one full-resolution multilabel NIfTI
- device: an explicit CUDA index; CPU fallback is rejected
- required task datasets: `291`, `292`, `293`, `294`, `295`, and `298`

`--fast`, `--fastest`, and `--save_lowres` remain prohibited. On a CUDA device
with less than 8 GiB total memory and a sufficiently large source, VoxelAtlas
uses upstream `--force_split`. That processes the input in chunks but does not
select a lower-resolution model or save a lower-resolution result.

## Controlled runtime storage

Provider state is stored outside Git beneath:

`VOXELATLAS_DATA_DIR/segmentation/providers/totalsegmentator/2.18.0`

The TotalSegmentator home, nnU-Net result directory, downloaded weights, sealed
weight manifest, and private acquisition logs all live below that root. The
controlled TotalSegmentator configuration disables anonymous usage statistics.
The weight manifest inventories every regular file by relative path, byte size,
and SHA-256; missing datasets, empty files, symlinks, or post-acquisition drift
make the provider unavailable.

## Canonical geometry bridge

The canonical source remains `derived/volume.npy` with axis order
`[slice,row,column]` and a voxel-index-to-Patient-LPS affine. An isolated worker
loads the NPY and descriptor in the qualified provider environment. It preserves
the array axes and converts the world affine from DICOM Patient LPS to NIfTI RAS
by pre-multiplying `diag(-1,-1,1,1)`. The source array/descriptor and output
NIfTI are all fingerprinted.

After inference, the same isolated worker verifies that the multilabel mask has
the exact input shape and affine, contains finite integer labels, begins at
background label 0, and never exceeds label 117. Phase 5B2 retains the validated
NIfTI in the private job directory.

## Process and failure boundary

Torch, nibabel, nnU-Net, and TotalSegmentator are never imported into the
FastAPI process. Every heavyweight operation runs through an argument-vector
subprocess with `shell=False`, a private working directory, explicit controlled
environment variables, deadline, cancellation polling, termination escalation,
and a bounded log budget. A CUDA tensor execution preflight runs immediately
before export/inference. Insufficient free memory, runtime drift, weight drift,
CPU fallback, reduced-resolution report flags, geometry drift, invalid labels,
timeout, cancellation, or non-zero exit prevents success.

## Public outcome and phase boundary

The durable Phase 5A job outcome records hashes, relative artifact identity,
CUDA/memory strategy, label inventory, timing, and the explicit
`clinical_validation=not_claimed` status. It never publishes patient paths or
provider tracebacks.

Phase 5C owns import of the qualified mask into VoxelAtlas canonical Patient LPS
label storage, source-binding revalidation, durable label descriptors, and
application-facing availability. Overlays, structure controls, derived surfaces,
and any clinical validation remain later phases.

## Target qualification correction

The first target run stopped safely at 5% before launching CUDA preflight. The
supervisor's argument validator treated the trusted multiline program passed to
`python -c` as an invalid filesystem-style argument, so no subprocess or log was
created. The corrected contract permits tab, newline, and carriage-return
characters only in the argument immediately following `-c`. NUL characters and
control characters in executable, path, and ordinary arguments remain rejected.
A regression test exercises the real supervisor with the exact CUDA preflight
program and retains the invalid-path and NUL rejection checks.

## Operator flow

First acquire and seal the weights:

```bash
python scripts/prepare_phase5b2_totalsegmentator_weights.py \
  --data-dir /var/lib/voxelatlas \
  --python $HOME/anaconda3/envs/voxelatlas-totalseg-2.18/bin/python \
  --accept-download
```

Then run one non-clinical qualification against an explicitly identified ready
canonical CT:

```bash
python scripts/run_phase5b2_totalsegmentator_qualification.py \
  --data-dir /var/lib/voxelatlas \
  --python $HOME/anaconda3/envs/voxelatlas-totalseg-2.18/bin/python \
  --study-id 0123456789abcdef0123456789abcdef \
  --device cuda:0 \
  --confirm-nonclinical
```

The first command downloads model weights. The second can take substantial time
and GPU memory. Run both in an existing shell so private diagnostic logs remain
available if a process fails.
