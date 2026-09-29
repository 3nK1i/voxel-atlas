# Phase 5B1 - TotalSegmentator Runtime Qualification

## Decision

Phase 5B1 fixes the first concrete provider boundary without running real
segmentation. The baseline is TotalSegmentator `2.18.0`, task `total`, CT only,
117 classes, full resolution, multilabel NIfTI output, and explicit CUDA
execution. TotalSegmentator remains outside the FastAPI process in an isolated
Python environment.

This step installs nothing, downloads no model weights, performs no inference,
creates no mask, and does not make the Phase 5A registry model available in the
running application. Runtime installation and real execution require explicit
target-workstation qualification in later Phase 5B work.

## Upstream contract reviewed

The official upstream repository at
`https://github.com/wasserth/TotalSegmentator` was reviewed on 2026-09-07 at
commit `a0d35d5996a9c096caed4184cededdbf2ede5268`. The published PyPI wheel and the
repository both declare TotalSegmentator `2.18.0`; the reviewed wheel SHA256 is
`6bc8721786925bfd972bc772a530ff651a1254e0737be47d15cb938ac2dd339a`.
Its default `total` task is the 117-class CT baseline and its normalized label-map
SHA256 is
`2f9caff9c6fc38df9a134d8258835f30cd33651da5a9d8b5dab77fbc7dac2d67`.
Full resolution is the normal model; `--fast`, `--fastest`, and `--save_lowres`
are therefore prohibited by the VoxelAtlas baseline. `--ml` produces one
multilabel NIfTI and `--report` produces a machine-readable provider report.

Two upstream convenience behaviors are intentionally not trusted by VoxelAtlas:

- DICOM CLI input may switch automatically between `total` and `total_mr`.
- an unavailable or invalid GPU may fall back to CPU.

VoxelAtlas will instead gate modality from its immutable canonical-volume
provenance before execution, export only a CT canonical NIfTI input, pass the
literal `total` task, require an explicit CUDA index, and validate the provider
report. Phase 5B2 must revalidate CUDA immediately before starting the worker and
must reject any resolved non-GPU execution. No MR model is registered by this
step.

## Qualification probe

`check_phase5b1_totalsegmentator_environment.py` launches the selected isolated
Python executable without a shell and returns only bounded structured fields. It
does not import PyTorch or TotalSegmentator into the web process. The probe
validates:

- the exact pinned TotalSegmentator version;
- importability of the official Python API;
- PyTorch and nnU-Net versions for provenance;
- task identity, CT modality, 117-class count, task-definition fingerprint, and
  non-licensed status;
- CUDA availability and a bounded GPU inventory.

Provider tracebacks, environment paths, patient paths, and stderr are never
copied into the public report. Missing runtimes, timeouts, malformed output, and
contract drift produce stable safe status codes.

Run the non-mutating target-runtime probe with:

```bash
python scripts/check_phase5b1_totalsegmentator_environment.py \
  --python /absolute/path/to/the/isolated/environment/bin/python
```

The separate dependency manifest pins only TotalSegmentator. PyTorch must be
installed for the target CUDA platform first and its resolved version is then
captured by the probe. Heavy provider dependencies remain absent from
`requirements/backend.txt`.

## Invocation contract for Phase 5B2

The pure invocation builder fixes `total`, `--ml`, `--report`, and an explicit
`gpu:<index>` mapping. It rejects CPU, automatic device selection, MR tasks,
resolution-reducing flags, ROI subsets, relative paths, non-NIfTI input/output,
and aliased input/output/report paths. It never uses a shell.

The current canonical patient artifact is `volume.npy`, which TotalSegmentator
does not accept. Phase 5B2 owns the bounded canonical-volume-to-NIfTI bridge and
the supervised provider worker. Phase 5C remains responsible for validating and
importing the resulting label mask into canonical Patient LPS space.

## Scope boundary

- Phase 5A job lifecycle, provenance, authentication, and API behavior are
  unchanged.
- The default model remains unavailable and no jobs can reach this runtime yet.
- No web UI, MPR overlay, structure panel, surface, or Phase 4 renderer changes.
- No patient data, runtime environment, provider cache, model weights, or output
  masks enter Git.
- Clinical accuracy, diagnostic suitability, and medical-device validation are
  not claimed.

## Validation

Run the source-level contract and full previous regression with:

```bash
bash scripts/run_phase5b1_checks.sh
```

Run the live target-runtime probe separately because source validation must stay
deterministic and must not depend on a heavyweight provider installation.
