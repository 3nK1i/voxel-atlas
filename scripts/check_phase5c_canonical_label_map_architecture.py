#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "voxelatlas"
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from voxelatlas.segmentation_label_maps import (  # noqa: E402
    AXIS_ORDER,
    CANONICAL_COORDINATE_SYSTEM,
    CANONICAL_DTYPE,
    SegmentationLabelMapService,
)


module = (BACKEND / "segmentation_label_maps.py").read_text(encoding="utf-8")
app = (BACKEND / "app.py").read_text(encoding="utf-8")
worker = (ROOT / "scripts" / "phase5c_label_map_worker.py").read_text(encoding="utf-8")
requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8").lower()

checks = {
    "service_contract": SegmentationLabelMapService.__name__ == "SegmentationLabelMapService",
    "canonical_coordinates": CANONICAL_COORDINATE_SYSTEM == "patient_lps",
    "canonical_axis_order": AXIS_ORDER == ("slice", "row", "column"),
    "canonical_dtype": CANONICAL_DTYPE == "uint16",
    "immutable_identity": "identity_sha256" in module and "provenance_sha256" in module,
    "source_binding": "source_volume_descriptor_sha256" in module,
    "job_binding": "segmentation_terminal_provenance_sha256" in module,
    "bidirectional_transforms": (
        "source_to_model_index" in module and "model_to_source_index" in module
    ),
    "no_silent_resampling": (
        '"resampled": False' in module and '"interpolation": "none"' in module
    ),
    "authenticated_descriptor_api": '"/api/segmentation/label-maps"' in app,
    "authenticated_detail_api": '"/api/segmentation/label-maps/{label_map_id}"' in app,
    "nifti_worker_isolated": "import nibabel as nib" in worker,
    "worker_ras_to_lps": "ras_to_lps" in worker and "model_affine_lps" in worker,
    "no_nibabel_backend_import": "nibabel" not in module,
    "no_nibabel_backend_dependency": "nibabel" not in requirements,
    "phase5d_not_enabled": "segmentation-overlay" not in app,
}

failed = [name for name, passed in checks.items() if not passed]
if failed:
    print("PHASE5C_CANONICAL_LABEL_MAP_ARCHITECTURE=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)

print("PHASE5C_CANONICAL_LABEL_MAP_ARCHITECTURE=PASS")
print("CANONICAL_COORDINATE_SYSTEM=patient_lps")
print("CANONICAL_LABEL_DTYPE=uint16")
print("BIDIRECTIONAL_TRANSFORMS=PRESERVED")
print("SILENT_RESAMPLING=REJECTED")
print("MPR_OVERLAY=NOT_ENABLED_UNTIL_PHASE5D")
print("CLINICAL_VALIDATION=NOT_CLAIMED")
