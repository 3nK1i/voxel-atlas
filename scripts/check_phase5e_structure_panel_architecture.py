#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_structures import (  # noqa: E402
    TOTAL_SEGMENTATOR_TOTAL_STRUCTURES,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    structures = (BACKEND / "voxelatlas" / "segmentation_structures.py").read_text(
        encoding="utf-8"
    )
    overlays = (BACKEND / "voxelatlas" / "segmentation_overlays.py").read_text(
        encoding="utf-8"
    )
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    panel = (ROOT / "web" / "js" / "segmentation-structure-panel.js").read_text(
        encoding="utf-8"
    )

    require(len(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES) == 117, "Total task taxonomy is incomplete")
    require(
        sorted(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES) == list(range(1, 118)),
        "Total task label contract is not contiguous",
    )
    require("build_structure_catalog" in overlays, "Overlay descriptor omits structure catalog")
    require("structure_catalog" in overlays, "Structure catalog is not public")
    require("segmentationStructurePanel" in html, "Structure panel markup is missing")
    require("SegmentationStructurePanel" in app, "Structure panel is not integrated")
    require("decodeSegmentationLabels" in app, "Local label decoding is missing")
    require("redrawSegmentationOverlays" in app, "Local overlay redraw is missing")
    require("data-structure-action" in panel, "Structure actions are missing")
    require("isolateStructure" in panel, "Structure isolation is missing")
    for forbidden in ("import torch", "import nibabel", "from totalsegmentator"):
        require(forbidden not in structures.lower(), f"Heavy runtime import found: {forbidden}")
    require("clinical-grade" not in (html + app + panel).lower(), "Clinical claim found")
    require("marching_cubes" not in (structures + overlays + app), "Phase 5F1 surface work leaked into 5E")

    print("PHASE5E_TOTAL_TASK_TAXONOMY=PASS")
    print("PHASE5E_PROVIDER_NEUTRAL_CATALOG=PASS")
    print("PHASE5E_LOCAL_PRESENTATION_CONTROLS=PASS")
    print("PHASE5E_HEAVY_RUNTIME_ISOLATION=PASS")
    print("PHASE5F1_SURFACES=NOT_ENABLED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5E_ARCHITECTURE_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
