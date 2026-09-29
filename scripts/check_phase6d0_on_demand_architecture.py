#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def function_slice(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def main() -> int:
    app_py = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
    config_py = (ROOT / "backend/voxelatlas/config.py").read_text(encoding="utf-8")
    workflow_py = (ROOT / "backend/voxelatlas/segmentation_workflow.py").read_text(encoding="utf-8")
    app_js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
    panel_js = (ROOT / "web/js/segmentation-workflow-panel.js").read_text(encoding="utf-8")
    index = (ROOT / "web/index.html").read_text(encoding="utf-8")
    surface_backend = (ROOT / "backend/voxelatlas/segmentation_surfaces.py").read_text(encoding="utf-8")

    ensure_mpr = function_slice(
        app_js,
        "async function ensureMprReady()",
        "function setMprCrosshairFromPointer",
    )
    ensure_volume = function_slice(
        app_js,
        "async function ensureCanonicalVolume(study)",
        "async function restoreReadyPatientVolume",
    )
    restore_volume = function_slice(
        app_js,
        "async function restoreReadyPatientVolume(message)",
        "async function refreshLatestStudy",
    )

    require("refreshSegmentationOverlayDescriptor" not in ensure_mpr,
            "Semantic segmentation still blocks the initial MPR path")
    for block, label in ((ensure_volume, "canonical volume"), (restore_volume, "restored volume")):
        mpr = block.find("await ensureMprReady();")
        dvr = block.find("await ensureVolumeRenderingFoundation();")
        workflow = block.find("void refreshSegmentationWorkflowStatus({ activateAvailable: false });")
        require(-1 not in (mpr, dvr, workflow) and mpr < dvr < workflow,
                f"{label} does not make MPR/direct volume ready before segmentation status")

    require("refreshSegmentationOverlayDescriptor(labelMapId)" in app_js,
            "Segmentation activation is not bound to an explicit label-map identity")
    require("descriptor.label_map_id !== labelMapId" in app_js,
            "Activated segmentation does not verify exact label-map binding")
    require("activateAvailable: false" in app_js,
            "Existing segmentation is still implicitly activated on initial study load")
    require("Start Segmentation" in index and "Use Segmentation" in panel_js,
            "Explicit on-demand segmentation action is missing")
    require("Cancel" in index and "Retry" in panel_js,
            "Segmentation cancel/retry presentation is incomplete")
    require("segmentationWorkflowProgress" in index and "finitePercent(workflow.progress)" in panel_js,
            "Provider-reported segmentation progress is not presented")
    require("setInterval" not in panel_js,
            "Fake timer-based segmentation progress is forbidden")

    require("VOXELATLAS_SEGMENTATION_PYTHON" in config_py,
            "Isolated segmentation runtime configuration is missing")
    require("TotalSegmentatorProvider" in app_py and "SegmentationWorkflowService" in app_py,
            "Qualified TotalSegmentator is not wired through the workflow service")
    require('bridge_script=REPOSITORY_ROOT / "scripts" / "phase5b2_nifti_worker.py"' in app_py,
            "Phase 5B2 qualified provider bridge was bypassed")
    require('import_worker_script=REPOSITORY_ROOT / "scripts" / "phase5c_label_map_worker.py"' in app_py,
            "Phase 5C canonical label-map import bridge was bypassed")
    require("BackgroundTasks" in app_py and "background_tasks.add_task" in app_py,
            "Segmentation execution is not detached from the start HTTP response")
    for route in (
        '/api/studies/latest/segmentation-workflow"',
        '/api/studies/latest/segmentation-workflow/start"',
        '/api/studies/latest/segmentation-workflow/cancel"',
    ):
        require(route in app_py, f"Missing Phase 6D0 route: {route}")
    require('response.headers["Cache-Control"] = "no-store"' in app_py,
            "Workflow responses are not explicitly no-store")
    require("Depends(require_username)" in app_py,
            "Workflow routes are not protected by the existing authentication dependency")

    require("def snapshot_latest" in workflow_py and "def request_start" in workflow_py,
            "On-demand workflow service contract is incomplete")
    require("if state == \"available\"" in workflow_py
            and "return SegmentationWorkflowStart(snapshot)" in workflow_py,
            "Existing valid segmentation is not reusable without recomputation")
    require("if state in NON_TERMINAL_JOB_STATES or state == \"finalizing\"" in workflow_py,
            "Duplicate active segmentation requests are not suppressed")
    require("self.job_service.create_job" in workflow_py,
            "Explicit Start Segmentation does not create the existing provider-neutral job")
    require("self.job_service.run_job(job_id)" in workflow_py,
            "Workflow bypasses the existing segmentation job execution lifecycle")
    require("self.label_map_service.import_succeeded_job" in workflow_py,
            "Successful provider output is not canonicalized through Phase 5C")
    require("self.job_service.cancel_job" in workflow_py,
            "Workflow cancellation bypasses the existing job lifecycle")
    require("segmentation provider is not available in Phase 6D0" in workflow_py,
            "Modality/provider gate is not explicit")
    require('supported_modalities=("CT",)' in (ROOT / "backend/voxelatlas/totalsegmentator_execution.py").read_text(encoding="utf-8"),
            "Qualified TotalSegmentator CT modality contract changed")
    require("MRI segmentation provider is deferred to Phase 7." in panel_js,
            "MRI provider roadmap boundary is not visible")

    # 6D0 changes workflow only. 6A/6B geometry remains authoritative.
    require("derived_from_accurate_surface" in surface_backend,
            "Phase 6A/6B immutable surface provenance chain is missing")
    combined = (workflow_py + app_py + app_js + panel_js + index).lower()
    for forbidden in (
        "volume-derived surface",
        "custom hu",
        "surface source selector",
        "presentation profile",
        "fidelity profile",
        "exploded view",
        "export stl",
        "export obj",
        "hausdorff",
    ):
        require(forbidden not in combined,
                f"Later Phase 6 functionality leaked into 6D0: {forbidden}")
    require("clinical-grade" not in combined and "diagnostic accuracy" not in combined,
            "Clinical claim found")

    print("PHASE6D0_VOLUME_MPR_FIRST=PASS")
    print("PHASE6D0_SEGMENTATION_OFF_INITIAL_CRITICAL_PATH=PASS")
    print("PHASE6D0_EXPLICIT_START_OR_USE=PASS")
    print("PHASE6D0_EXISTING_RESULT_REUSE=PASS")
    print("PHASE6D0_DUPLICATE_ACTIVE_JOB_PREVENTION=PASS")
    print("PHASE6D0_REAL_PROVIDER_PROGRESS=PASS")
    print("PHASE6D0_CANCEL_RETRY=PASS")
    print("PHASE6D0_PHASE5B2_PROVIDER_REUSE=PASS")
    print("PHASE6D0_PHASE5C_CANONICAL_IMPORT=PASS")
    print("PHASE6D0_CT_ONLY_MODALITY_GATE=PASS")
    print("PHASE6D0_MRI_PROVIDER_DEFERRED_TO_PHASE7=PASS")
    print("PHASE6AB_GEOMETRY_PRESERVED=PASS")
    print("PHASE6D0_ROADMAP_BOUNDARY=PASS")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6D0_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
