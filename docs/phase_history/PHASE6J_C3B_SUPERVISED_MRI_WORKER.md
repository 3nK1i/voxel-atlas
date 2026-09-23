# Phase 6J-C3B — supervised MRI worker contract

Baseline: `5692e5065a1a50ec3e05630500ecd6c19c54a577` on `phase6-accurate-surfaces`.

An isolated `MRIWorkerExecutor` implements a **future callable** (not an activated provider): it requires explicit execution authorization plus the study-bound canonical MR source, validates source hashes, the C1 task, pinned C2 assets and mapping, then supervises a small CUDA preflight, the C3A canonical NIfTI export, a pinned `total_mr` multilabel subprocess, and independent C3A mask inspection. Existing CT `total` runtime, worker, provider registry, and UI remain unchanged. The established generic CT process supervisor is reused **only** for safe subprocess start, cancellation, bounded runtime and private logs.

The 6 GB class is restricted to `fastest` (6 mm) *trial mode*, contingent on a 4 GiB CUDA-free-memory preflight. This is a preliminary attempt policy, not proof that inference fits or that the output is clinically suitable. Default/fast remain selectable on sufficiently large GPUs in a future supervised run. GPU visibility is scoped to a single device. The model CLI and its structured report must be tested against the user's installed pinned runtime before any model run is accepted.

The default `explicit_model_authorization=False` prevents accidental model execution. Even an explicitly authorized call is not wired to UI, automatic worker startup or a job provider in C3B. C4 must bind canonical source, study/series, job identity, cancellation, and model mode; C5 must separately validate actual inference, GPU/disk requirements and output on a suitable non-identifying MRI study. No patient data, model weights, logs, runtime configuration or private artifacts belong in Git or review ZIPs.

C3B acceptance: guarded application; isolated synthetic fake-execution and negative tests; real generic-supervisor timeout/cancellation tests; complete C3A/C2/CT regressions; source review. `MRI_EXECUTION_ENABLED=NO` until later explicit authorization. No real MRI inference, provider registration, MPR overlays, surfaces, deployment, or clinical validation is claimed by this step.
