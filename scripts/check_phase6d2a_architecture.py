#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "web/js/reconstruction-visualization-mode.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/phase_history/PHASE6D2A_VISUALIZATION_MODE_CONTROLLER.md").read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise SystemExit(f"{label}=FAIL")
    print(f"{label}=PASS")


require(all(f'id: "{mode}"' in MODULE for mode in ("volume", "surface", "combined")), "PHASE6D2A_MODE_CATALOG")
require(all(f'id: "{source}"' in MODULE for source in ("volume-derived", "segmentation-derived")), "PHASE6D2A_SURFACE_SOURCE_CATALOG")
require("selectedSurfaceSources" in MODULE and "visibility" in MODULE, "PHASE6D2A_MODE_SOURCE_SEPARATION")
require("fetch(" not in MODULE.lower() and "/api/" not in MODULE.lower(), "PHASE6D2A_PRESENTATION_ONLY")
require("requestMode" in MODULE and "surface-unavailable" in MODULE and "volume-unavailable" in MODULE, "PHASE6D2A_FAIL_CLOSED_MODE_REQUEST")
require("6D2B" in DOC and "6D2C" in DOC and "6D2D" in DOC, "PHASE6D2A_INCREMENT_BOUNDARY")
require("Phase 6E" in DOC and "Phase 6F" in DOC, "PHASE6D2A_LATER_PHASE_BOUNDARY")
require("Clinical validation is not claimed" in DOC, "CLINICAL_VALIDATION_NOT_CLAIMED")
print("PHASE6D2A_ARCHITECTURE_OK=YES")
