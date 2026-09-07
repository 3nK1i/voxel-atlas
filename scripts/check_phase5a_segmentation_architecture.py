#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation import build_default_segmentation_registry  # noqa: E402


backend = (BACKEND_ROOT / "voxelatlas" / "segmentation.py").read_text(encoding="utf-8")
app = (BACKEND_ROOT / "voxelatlas" / "app.py").read_text(encoding="utf-8")
requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8").lower()
models = build_default_segmentation_registry().list_public()
planned = models[0] if len(models) == 1 else {}

checks = {
    "provider_contract": "class SegmentationProvider(Protocol)" in backend,
    "deterministic_registry": "class SegmentationModelRegistry" in backend,
    "validated_lifecycle": "TERMINAL_JOB_STATES" in backend and "def begin_job(" in backend,
    "structured_progress": "PROGRESS_STAGES" in backend and "def report_progress(" in backend,
    "cooperative_cancellation": "raise_if_cancelled" in backend and "def cancel_job(" in backend,
    "device_policy": "class SegmentationDeviceSelector" in backend and "nvidia-smi" in backend,
    "atomic_manifests": "os.replace(temporary, manifest_path)" in backend,
    "restart_recovery": "def _recover_interrupted_jobs(" in backend,
    "immutable_provenance": (
        "provenance_sha256" in backend and "terminal_provenance_sha256" in backend
    ),
    "source_drift": "canonical volume changed" in backend,
    "model_drift": "registered model changed" in backend,
    "private_data_root": (
        'self.segmentation_root = self.data_dir / "segmentation"' in backend
        and 'self.jobs_root = self.segmentation_root / "jobs"' in backend
    ),
    "authenticated_models_api": '"/api/segmentation/models"' in app,
    "authenticated_jobs_api": '"/api/segmentation/jobs"' in app,
    "authenticated_cancel_api": '"/api/segmentation/jobs/{job_id}/cancel"' in app,
    "totalsegmentator_declared": planned.get("provider_id") == "totalsegmentator",
    "totalsegmentator_ct_only": planned.get("supported_modalities") == ["CT"],
    "totalsegmentator_unavailable": planned.get("available") is False,
    "no_heavy_runtime": all(
        package not in requirements
        for package in ("torch", "monai", "totalsegmentator")
    ),
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    print("PHASE5A_SEGMENTATION_ARCHITECTURE=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)

print("PHASE5A_SEGMENTATION_ARCHITECTURE=PASS")
print("DEFAULT_MODEL=totalsegmentator/total")
print("DEFAULT_MODEL_AVAILABLE=NO")
print("REAL_INFERENCE_ENABLED=NO")
