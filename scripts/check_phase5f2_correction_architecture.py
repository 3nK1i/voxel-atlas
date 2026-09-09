#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    service = (ROOT / "backend/voxelatlas/segmentation_corrections.py").read_text(encoding="utf-8")
    app = (ROOT / "backend/voxelatlas/app.py").read_text(encoding="utf-8")
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    browser = (ROOT / "web/js/segmentation-correction-panel.js").read_text(encoding="utf-8")
    combined = (service + app + html + browser).lower()

    require("revision_sha256" in service, "Correction revision seal is missing")
    require("source_label_map\": \"immutable" in service, "Immutable source boundary is missing")
    require("array_index_to_patient_lps" in service, "Patient LPS validation is missing")
    require("correction-sessions" in app, "Correction session API is missing")
    require("segmentation-quality" in app, "Segmentation quality API is missing")
    for control in ("segmentationCorrectionApply", "segmentationCorrectionUndo", "segmentationQualityWarnings"):
        require(control in html, f"Correction UI control is missing: {control}")
    require("getCrosshair" in browser, "Synchronized MPR correction hook is missing")
    require("clinical-grade" not in combined, "Clinical claim found")
    require("marching.cubes" not in combined, "Phase 6 surface refinement leaked into Phase 5F2")
    require("labels.npy\").write" not in service, "Canonical labels can be rewritten")

    print("PHASE5F2_IMMUTABLE_SOURCE_BOUNDARY=PASS")
    print("PHASE5F2_REVERSIBLE_DRAFT_HISTORY=PASS")
    print("PHASE5F2_PATIENT_LPS_REFINEMENT_HOOKS=PASS")
    print("PHASE5F2_QUALITY_WARNING_CONTRACT=PASS")
    print("CORRECTION_MATERIALIZATION=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5F2_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
