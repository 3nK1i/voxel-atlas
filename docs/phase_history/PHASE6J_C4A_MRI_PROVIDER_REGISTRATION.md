# Phase 6J-C4A — MRI provider descriptor and prerequisite qualification

Base: `f50d8eb7f4a9d166365ab378006e2551b78127cc`, branch `phase6-accurate-surfaces`.

- Register `totalsegmentator/total_mr` as a distinct **unavailable descriptor** in the default application registry; preserve existing `totalsegmentator/total` CT provider behavior and injected services.
- Optional `VOXELATLAS_MRI_PYTHON` selects an independent MRI interpreter; it does not alter `VOXELATLAS_SEGMENTATION_PYTHON` (CT). With no MRI interpreter configured, report an unavailable MRI runtime without probing or downloading models.
- With an MRI interpreter configured, perform read-only C1 runtime, installed C2 task mapping, and sealed asset verification at app creation. No model command, weight download, study write, or worker invocation occurs in C4A.
- Source qualification is per selected canonical MR study/series, not a global provider property. `qualify_mri_provider(source=...)` reuses the B2A stored-source check; missing or invalid source cannot be declared qualified. Runtime and asset qualification alone cannot qualify a study.
- `execution_authorized=False` and descriptor `available=False` are **unconditional in C4A**, even if source, runtime, and weights are qualified. No executable MRI provider is registered. C4B will add a study-bound execution adapter, C4C UI integration, and C5 controlled real inference acceptance.
- Never commit MRI model weights or patient study artifacts. Synthetic C4A unit tests contain no patient content.

Manual acceptance: inspect `/api/segmentation/models` and the existing MRI/CT study workflow using the normal local development preview after local automated validation, without enabling MRI model execution. C4A does not promise real MRI model inference or anatomy correctness.
