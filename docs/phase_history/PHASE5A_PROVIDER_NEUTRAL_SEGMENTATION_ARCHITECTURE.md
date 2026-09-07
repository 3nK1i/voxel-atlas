# Phase 5A - Provider-Neutral Segmentation Architecture

## Decision

Phase 5A establishes the provider-neutral segmentation control plane without
installing or running a segmentation model. The accepted Phase 4 canonical
patient volume remains the immutable source of truth. No mask, overlay,
structure panel, or surface is introduced by this step.

## Model and provider boundary

`SegmentationProvider` separates orchestration from provider-specific runtime
logic. Each model has a validated descriptor with stable provider/model
identity, provider and model versions, task, capabilities, explicit CT/MR
compatibility, availability, and execution requirements. Registry output is
deterministically ordered and duplicate identities are rejected.

The default registry declares `totalsegmentator/total` as the planned
full-resolution CT baseline. It is deliberately marked unavailable, with
unqualified runtime/model versions, until Phase 5B installs and verifies the
exact runtime. MR is not accepted by this CT model.

## Job lifecycle

The durable lifecycle is:

`queued -> starting -> running -> succeeded`

Running work may enter `cancelling -> cancelled`, queued work can be cancelled
immediately, and any non-terminal state may end as `failed`. Invalid transitions
are rejected. Progress uses ordered stages and a monotonic 0-100 percentage with
a bounded human-readable status message.

Cancellation is cooperative and idempotent. The provider context exposes a
cancellation check and `raise_if_cancelled()`. Phase 5A intentionally does not
add a background inference scheduler; `run_job()` is the internal synchronous
worker boundary that Phase 5B can call from its qualified execution mechanism.

## Persistence, recovery, and provenance

Jobs are stored only under:

`VOXELATLAS_DATA_DIR/segmentation/jobs/seg-<32 lowercase hex>/manifest.json`

Manifests are written through a same-directory temporary file, flushed, and
atomically replaced. Runtime job data is not stored in the source tree. Strict
identifier validation prevents path traversal, and public responses never
contain internal filesystem paths.

Immutable provenance binds every job to:

- source study and series identity;
- source modality;
- canonical-volume creation time, descriptor SHA256, and artifact SHA256;
- provider/model identity and versions plus descriptor SHA256;
- validated canonical parameters;
- selected CPU/CUDA device details;
- creation, start, and completion timestamps;
- terminal outcome.

The immutable creation provenance has its own canonical SHA256 integrity check.
On completion, a separate sealed terminal-provenance record binds creation,
start, and completion timestamps to the terminal state and outcome. Before a job
starts, the service revalidates both the canonical-volume descriptor/artifact and
the registered/runtime model descriptor. Source or model drift is rejected.
When the service starts, persisted non-terminal jobs are closed as failed with a
safe `interrupted` outcome instead of being silently resumed in an unknown
state.

## Device policy

CUDA discovery uses a bounded `nvidia-smi` subprocess and requires no PyTorch,
MONAI, or TotalSegmentator import. The policy accepts `auto`, `cpu`, or an exact
`cuda:<index>` request. Automatic selection is deterministic: compatible GPUs
are ordered by available memory, total memory, and then device index. CPU is a
fallback only when the chosen model explicitly permits CPU execution. Invalid,
missing, unsupported, or under-memory explicit devices are never silently
replaced.

## Authenticated API

All Phase 5A endpoints use the existing opaque-session authentication boundary
and return `Cache-Control: no-store`:

- `GET /api/segmentation/models`
- `GET /api/segmentation/devices`
- `POST /api/segmentation/jobs`
- `GET /api/segmentation/jobs`
- `GET /api/segmentation/jobs/{job_id}`
- `POST /api/segmentation/jobs/{job_id}/cancel`

The default production registry cannot create a job in Phase 5A because its only
planned model is unavailable. Tests inject a lightweight fake provider to
qualify the contract without performing inference.

## Safety and scope boundary

- No heavyweight ML dependency is added.
- No model weights or provider runtime are installed.
- No segmentation inference runs in the default application.
- No label mask is generated or imported.
- No MPR overlay, structure panel, surface mesh, or web UI is changed.
- Canonical voxels, Patient LPS geometry, Phase 4 rendering, and production data
  boundaries are unchanged.
- Clinical validation, diagnostic suitability, and medical-device status are
  not claimed.

Phase 5B may implement the exact TotalSegmentator CT provider behind this
contract. Phase 5C remains responsible for validating and importing provider
label masks into canonical Patient LPS space.

## Validation

Run from the repository root with the project environment active:

```bash
bash scripts/run_phase5a_checks.sh
```

The compact runner covers the Phase 5A unit/API contract, architecture probe,
full Phase 4 closure regression, Python compilation, shell syntax, patient-data
Git safety, heavyweight-dependency exclusion, and diff whitespace.
