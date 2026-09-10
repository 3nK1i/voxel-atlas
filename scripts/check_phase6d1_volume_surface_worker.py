#!/usr/bin/env python3
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HEADER = struct.Struct("<4s7I")

def sha(path): return sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    args=ap.parse_args()
    from voxelatlas.segmentation_surface_runtime import SegmentationSurfaceRuntimeQualifier
    runtime=SegmentationSurfaceRuntimeQualifier().qualify(args.python)
    if not runtime.qualified or not runtime.runtime_fingerprint_sha256:
        print("PHASE6D1_WORKER_RUNTIME=FAIL"); return 1
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); volume_path=root/"volume.npy"; request_path=root/"request.json"; output=root/"surface.vxvs"
        volume=np.zeros((8,9,10), dtype=np.float32)
        volume[2:6,2:7,3:8]=800.0
        np.save(volume_path, volume, allow_pickle=False)
        before=sha(volume_path)
        request={
            "schema_version":1,"operation":"extract_volume_isosurface","extraction":"marching_cubes_isovalue",
            "source_type":"canonical_volume","source_volume":"immutable","source_modality":"CT","source_intensity_units":"HU",
            "source_value_range":[0.0,800.0],"source_descriptor_sha256":"1"*64,"expected_volume_sha256":before,
            "shape":list(volume.shape),"array_index_to_patient_lps":[[0,0,2,10],[0,3,0,20],[4,0,0,30],[0,0,0,1]],
            "isovalue":300.0,"coordinate_system":"patient_lps","expected_runtime_fingerprint_sha256":runtime.runtime_fingerprint_sha256,
            "max_vertices":2000000,"max_triangles":4000000,"max_payload_bytes":160*1024*1024,"clinical_validation":"not_claimed",
        }
        request_path.write_text(json.dumps(request, sort_keys=True, separators=(",",":")), encoding="utf-8")
        cp=subprocess.run([args.python,"-I",str(ROOT/"scripts/phase6d1_volume_surface_worker.py"),"--volume-npy",str(volume_path),"--request-json",str(request_path),"--output-surface",str(output)],capture_output=True,text=True,check=False,timeout=120)
        if cp.returncode != 0: print(cp.stdout); print(cp.stderr); return 1
        report=json.loads([x for x in cp.stdout.splitlines() if x.strip()][-1])
        payload=output.read_bytes(); header=HEADER.unpack_from(payload)
        magic,version,vertices,indices,pos_bytes,norm_bytes,index_bytes,flags=header
        if magic != b"VXVS" or version != 1 or flags != 1 or vertices<=0 or indices<=0 or indices%3: return 1
        if sha(volume_path) != before: return 1
        if report.get("coordinate_system") != "patient_lps" or report.get("source_volume") != "immutable": return 1
        if report.get("payload_sha256") != sha256(payload).hexdigest(): return 1
        if report.get("degenerate_triangle_count") != 0: return 1
        if report.get("degenerate_triangle_fraction") != 0.0: return 1
        if report.get("raw_triangle_count") != report.get("triangle_count"): return 1
        if report.get("max_degenerate_triangle_fraction") != 1e-4: return 1
        print(f"VERTEX_COUNT={vertices}")
        print(f"TRIANGLE_COUNT={indices//3}")
        print("SOURCE_VOLUME=IMMUTABLE")
        print("GEOMETRY_CHAIN=PATIENT_LPS")
        print("DEGENERATE_FACE_CLEANUP=BOUNDED")
        print("PHASE6D1_WORKER_SMOKE_OK=YES")
        return 0
if __name__ == "__main__": raise SystemExit(main())
