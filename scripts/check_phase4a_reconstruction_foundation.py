#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
backend = (ROOT / "backend" / "voxelatlas" / "anatomy_reconstruction.py").read_text(encoding="utf-8")
app = (ROOT / "backend" / "voxelatlas" / "app.py").read_text(encoding="utf-8")
requirements = (ROOT / "requirements" / "backend.txt").read_text(encoding="utf-8").lower()

checks = {
    "service": "class AnatomyReconstructionService" in backend,
    "provider_protocol": "class AnatomyReconstructor(Protocol)" in backend,
    "patient_lps_contract": 'CANONICAL_COORDINATE_SYSTEM = "patient_lps"' in backend,
    "millimetre_contract": 'CANONICAL_LENGTH_UNITS = "mm"' in backend,
    "private_mesh_contract": 'vertices_lps_mm=vertices' in backend and 'artifact_format=CANONICAL_ARTIFACT_FORMAT' in backend,
    "source_identity": "source_volume_descriptor_sha256" in backend,
    "ct_skull": 'source.modality == "CT" and source.intensity_units == "HU"' in backend,
    "mr_brain": 'source.modality == "MR"' in backend,
    "status_endpoint": '"/api/studies/latest/reconstruction"' in app,
    "no_store": 'response.headers["Cache-Control"] = "no-store"' in app,
    "no_heavy_runtime": all(
        package not in requirements
        for package in ("scipy", "scikit-image", "simpleitk", "trimesh", "pyvista")
    ),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print("PHASE4A_RECONSTRUCTION_FOUNDATION=FAIL")
    print("FAILED=" + ",".join(failed))
    raise SystemExit(1)
print("PHASE4A_RECONSTRUCTION_FOUNDATION=PASS")
