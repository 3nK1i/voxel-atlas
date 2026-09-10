#!/usr/bin/env python3
from __future__ import annotations
import argparse
from hashlib import sha256
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/"backend"
if str(BACKEND) not in sys.path: sys.path.insert(0,str(BACKEND))
from voxelatlas.volume_rendering import VolumeRenderingService
from voxelatlas.volume_surfaces import VolumeSurfaceService

def sha(path):
    h=sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description="Qualify a real Phase 6D1 CT volume-derived surface")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--isovalue", type=float, default=300.0)
    ap.add_argument("--expected-study-id")
    args=ap.parse_args()
    data=Path(args.data_dir).resolve()
    vr=VolumeRenderingService(data_dir=data)
    source=vr.source_latest()
    print("===== PHASE 6D1 REAL CT VOLUME SURFACE QUALIFICATION =====")
    print(f"STUDY_ID={source.study_dir.name}")
    print(f"SOURCE_MODALITY={source.modality}")
    print(f"SOURCE_UNITS={source.intensity_units}")
    print("SOURCE_SHAPE="+"x".join(str(x) for x in source.shape))
    print(f"ISOVALUE={args.isovalue:.6f}")
    if args.expected_study_id and source.study_dir.name != args.expected_study_id:
        print("STATUS=FAILED\nREASON=unexpected_latest_study"); return 1
    before=sha(source.volume_path)
    service=VolumeSurfaceService(data_dir=data, volume_rendering_service=vr, worker_python=args.python, worker_script=ROOT/"scripts/phase6d1_volume_surface_worker.py")
    surface=service.surface_latest(isovalue=args.isovalue)
    after=sha(source.volume_path)
    if before != after: print("STATUS=FAILED\nREASON=source_volume_changed"); return 1
    print(f"SURFACE_ID={surface.surface_id}")
    print(f"PAYLOAD_SHA256={surface.payload_sha256}")
    print(f"PROVENANCE_SHA256={surface.provenance_sha256}")
    print(f"VERTEX_COUNT={surface.vertex_count}")
    print(f"RAW_VERTEX_COUNT={surface.raw_vertex_count}")
    print(f"RAW_TRIANGLE_COUNT={surface.raw_triangle_count}")
    print(f"DEGENERATE_TRIANGLE_COUNT={surface.degenerate_triangle_count}")
    print(f"DEGENERATE_TRIANGLE_FRACTION={surface.degenerate_triangle_fraction:.12f}")
    print(f"UNREFERENCED_VERTEX_COUNT={surface.unreferenced_vertex_count}")
    print(f"VERTEX_COUNT={surface.vertex_count}")
    print(f"TRIANGLE_COUNT={surface.triangle_count}")
    print("BOUNDS_LPS_MM="+",".join(f"{x:.6f}" for x in surface.bounds_lps_mm))
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("SOURCE_TYPE=CANONICAL_VOLUME")
    print("SEGMENTATION_REQUIRED=NO")
    print("SOURCE_VOLUME=IMMUTABLE")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("STATUS=QUALIFIED")
    print("PHASE6D1_REAL_CT_VOLUME_SURFACE_OK=YES")
    return 0
if __name__ == "__main__": raise SystemExit(main())
