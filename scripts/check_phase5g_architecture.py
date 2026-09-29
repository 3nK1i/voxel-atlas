#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_qualification import (  # noqa: E402
    PHASE5_QUALIFICATION_SCHEMA_VERSION,
    Phase5QualificationBudget,
)


def main() -> int:
    module = BACKEND / "voxelatlas" / "segmentation_qualification.py"
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    forbidden = {"torch", "nibabel", "nnunetv2", "totalsegmentator"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not imports.intersection(forbidden)
    assert PHASE5_QUALIFICATION_SCHEMA_VERSION == 1
    budget = Phase5QualificationBudget()
    assert budget.metadata_seconds > 0
    assert budget.overlays_seconds > 0
    assert budget.surface_seconds > 0
    print("PHASE5G_ARCHITECTURE_OK=YES")
    print("HEAVY_RUNTIME_DEPENDENCIES=ISOLATED")
    print("MODEL_COMPARISON_RANKING=NOT_CLAIMED")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
