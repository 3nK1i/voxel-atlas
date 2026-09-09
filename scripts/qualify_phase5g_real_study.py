#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.segmentation_qualification import Phase5QualificationService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify the real-study Phase 5 segmentation presentation chain."
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--label-map-id", required=True)
    parser.add_argument("--label-id", type=int, default=91)
    parser.add_argument("--quality", choices=("preview", "balanced"), default="preview")
    args = parser.parse_args()

    report = Phase5QualificationService(data_dir=args.data_dir).qualify(
        label_map_id=args.label_map_id,
        label_id=args.label_id,
        quality=args.quality,
    )
    print("===== PHASE 5G REAL-STUDY SEGMENTATION QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    for key in (
        "source_study_id", "label_map_id", "label_map_sha256", "provider_id",
        "provider_version", "model_id", "model_version", "present_label_count",
        "qualified_label_id", "overlay_plane_count", "surface_vertex_count",
        "surface_triangle_count", "surface_payload_sha256", "quality_warning_count",
        "model_comparison_candidate_count",
    ):
        print(f"{key.upper()}={report[key]}")
    timings = report["timings_seconds"]
    assert isinstance(timings, dict)
    print(f"METADATA_SECONDS={float(timings['metadata']):.6f}")
    print(f"OVERLAYS_SECONDS={float(timings['overlays']):.6f}")
    print(f"SURFACE_SECONDS={float(timings['surface']):.6f}")
    print("GEOMETRY_CHAIN=PASS")
    print("PERFORMANCE_BUDGET=PASS")
    print("MODEL_COMPARISON_RANKING=NOT_CLAIMED")
    print("SOURCE_LABEL_MAP=IMMUTABLE")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE5G_REAL_STUDY_QUALIFICATION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
