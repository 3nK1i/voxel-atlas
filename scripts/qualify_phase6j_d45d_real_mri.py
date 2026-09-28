#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
from hashlib import sha256
from math import isfinite
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from voxelatlas.volume_rendering import VolumeRenderingService  # noqa: E402
from voxelatlas.volume_surfaces import (  # noqa: E402
    DEFAULT_MR_NORMALIZED_ISOVALUE,
    MAX_VOLUME_SURFACE_PAYLOAD_BYTES,
    MAX_VOLUME_SURFACE_TRIANGLES,
    MAX_VOLUME_SURFACE_VERTICES,
    MRI_NORMALIZATION_HIGH_PERCENTILE,
    MRI_NORMALIZATION_LOW_PERCENTILE,
    MRI_NORMALIZATION_PROFILE,
    MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
    MRI_SURFACE_INTENSITY_UNITS,
    VolumeSurfaceService,
)

QUALIFICATION_ISOVALUES = (0.35, 0.50, 0.65)


def _runtime_executable_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify the current real MRI Direct-MR surface at normalized isovalues "
            "0.35, 0.50 and 0.65 without modifying patient data."
        )
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--surface-python", required=True, type=Path)
    parser.add_argument("--expected-study-id")
    parser.add_argument("--manual-preferred-isovalue", type=float)
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    surface_python = _runtime_executable_path(args.surface_python)
    if not surface_python.is_file():
        raise SystemExit("Qualified surface Python is unavailable")

    volume_service = VolumeRenderingService(data_dir=data_dir)
    source = volume_service.source_latest()
    study_id = source.study_dir.name
    if args.expected_study_id and study_id != args.expected_study_id:
        raise SystemExit("Latest study does not match --expected-study-id")
    if source.modality != "MR" or source.intensity_units != "modality":
        raise SystemExit("D4.5D real-study qualification requires MR/modality input")
    if source.volume_path.is_symlink() or not source.volume_path.is_file():
        raise SystemExit("Canonical MRI volume artifact is unsafe")

    before_sha = file_sha256(source.volume_path)

    descriptor_service = VolumeSurfaceService(
        data_dir=data_dir,
        volume_rendering_service=volume_service,
        worker_python=str(surface_python),
        worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
    )
    descriptor = descriptor_service.descriptor_latest()
    if descriptor.get("available") is not True or descriptor.get("backend_available") is not True:
        raise SystemExit("Direct MR backend is unavailable")
    if descriptor.get("source_modality") != "MR":
        raise SystemExit("Direct MR descriptor modality changed")
    if descriptor.get("source_intensity_units") != "modality":
        raise SystemExit("Direct MR source intensity contract changed")
    if descriptor.get("surface_intensity_units") != MRI_SURFACE_INTENSITY_UNITS:
        raise SystemExit("Direct MR normalized-signal contract changed")
    if descriptor.get("surface_isovalue_range") != [0.0, 1.0]:
        raise SystemExit("Direct MR normalized-isovalue range changed")
    if descriptor.get("default_isovalue") != DEFAULT_MR_NORMALIZED_ISOVALUE:
        raise SystemExit("Direct MR neutral default changed")
    if descriptor.get("segmentation_required") is not False:
        raise SystemExit("Direct MR unexpectedly depends on segmentation")
    normalization = descriptor.get("normalization")
    if not isinstance(normalization, dict):
        raise SystemExit("Direct MR normalization metadata is unavailable")
    expected_normalization = {
        "profile": MRI_NORMALIZATION_PROFILE,
        "low_percentile": MRI_NORMALIZATION_LOW_PERCENTILE,
        "high_percentile": MRI_NORMALIZATION_HIGH_PERCENTILE,
        "clip_to_unit_interval": True,
        "gaussian_sigma_mm": MRI_PRESENTATION_GAUSSIAN_SIGMA_MM,
        "semantic_identity": "none",
    }
    if normalization != expected_normalization:
        raise SystemExit("Direct MR normalization metadata changed")

    preferred = args.manual_preferred_isovalue
    if preferred is not None:
        if not isfinite(preferred) or all(abs(preferred - value) > 1e-12 for value in QUALIFICATION_ISOVALUES):
            raise SystemExit("--manual-preferred-isovalue must be one of 0.35, 0.50, 0.65")

    results: list[dict[str, object]] = []
    for level in QUALIFICATION_ISOVALUES:
        service = VolumeSurfaceService(
            data_dir=data_dir,
            volume_rendering_service=volume_service,
            worker_python=str(surface_python),
            worker_script=ROOT / "scripts" / "phase6d1_volume_surface_worker.py",
        )
        started = perf_counter()
        surface = service.surface_latest(isovalue=level)
        elapsed = perf_counter() - started

        if surface.study_id != study_id:
            raise SystemExit(f"Direct MR surface study identity changed at {level:.2f}")
        if surface.source_modality != "MR" or surface.intensity_units != MRI_SURFACE_INTENSITY_UNITS:
            raise SystemExit(f"Direct MR modality/intensity contract changed at {level:.2f}")
        if surface.coordinate_system != "patient_lps":
            raise SystemExit(f"Direct MR surface is not in Patient LPS at {level:.2f}")
        if surface.vertex_count <= 0 or surface.vertex_count > MAX_VOLUME_SURFACE_VERTICES:
            raise SystemExit(f"Direct MR vertex budget failed at {level:.2f}")
        if surface.triangle_count <= 0 or surface.triangle_count > MAX_VOLUME_SURFACE_TRIANGLES:
            raise SystemExit(f"Direct MR triangle budget failed at {level:.2f}")
        if len(surface.payload) <= 0 or len(surface.payload) > MAX_VOLUME_SURFACE_PAYLOAD_BYTES:
            raise SystemExit(f"Direct MR payload budget failed at {level:.2f}")
        if surface.degenerate_triangle_count < 0 or not isfinite(surface.degenerate_triangle_fraction):
            raise SystemExit(f"Direct MR cleanup statistics are invalid at {level:.2f}")
        if surface.degenerate_triangle_fraction > 1e-4:
            raise SystemExit(f"Direct MR degenerate-triangle budget failed at {level:.2f}")
        if len(surface.bounds_lps_mm) != 6 or not all(isfinite(value) for value in surface.bounds_lps_mm):
            raise SystemExit(f"Direct MR Patient-LPS bounds are invalid at {level:.2f}")
        if not isfinite(elapsed) or elapsed <= 0:
            raise SystemExit(f"Direct MR extraction timing is invalid at {level:.2f}")
        if file_sha256(source.volume_path) != before_sha:
            raise SystemExit(f"Canonical MRI volume changed during {level:.2f} extraction")

        results.append({
            "isovalue": level,
            "elapsed_seconds": elapsed,
            "surface_id": surface.surface_id,
            "payload_sha256": surface.payload_sha256,
            "provenance_sha256": surface.provenance_sha256,
            "vertex_count": surface.vertex_count,
            "triangle_count": surface.triangle_count,
            "payload_bytes": len(surface.payload),
            "degenerate_triangle_count": surface.degenerate_triangle_count,
            "degenerate_triangle_fraction": surface.degenerate_triangle_fraction,
            "bounds_lps_mm": surface.bounds_lps_mm,
        })
        del surface
        del service
        gc.collect()

    if len({str(result["payload_sha256"]) for result in results}) != len(results):
        raise SystemExit("Direct MR qualification isovalues did not produce distinct geometry payloads")
    if file_sha256(source.volume_path) != before_sha:
        raise SystemExit("Canonical MRI volume changed during D4.5D qualification")

    print("===== PHASE 6J-D4.5D REAL MRI DIRECT-SURFACE QUALIFICATION =====")
    print("STATUS=QUALIFIED")
    print(f"SOURCE_STUDY_ID={study_id}")
    print(f"SOURCE_MODALITY={source.modality}")
    print(f"SOURCE_INTENSITY_UNITS={source.intensity_units}")
    print("SOURCE_SHAPE=" + "x".join(str(value) for value in source.shape))
    print(f"SOURCE_VOLUME_SHA256={before_sha}")
    print(f"DIRECT_MR_NORMALIZATION_PROFILE={MRI_NORMALIZATION_PROFILE}")
    print(f"DIRECT_MR_NORMALIZATION_PERCENTILES={MRI_NORMALIZATION_LOW_PERCENTILE:g},{MRI_NORMALIZATION_HIGH_PERCENTILE:g}")
    print(f"DIRECT_MR_GAUSSIAN_SIGMA_MM={MRI_PRESENTATION_GAUSSIAN_SIGMA_MM:g}")
    print(f"DIRECT_MR_DEFAULT_ISOVALUE={DEFAULT_MR_NORMALIZED_ISOVALUE:.2f}")
    for result in results:
        tag = f"{float(result['isovalue']):.2f}".replace(".", "_")
        print(f"DIRECT_MR_{tag}_WALL_SECONDS={float(result['elapsed_seconds']):.3f}")
        print(f"DIRECT_MR_{tag}_SURFACE_ID={result['surface_id']}")
        print(f"DIRECT_MR_{tag}_PAYLOAD_SHA256={result['payload_sha256']}")
        print(f"DIRECT_MR_{tag}_PROVENANCE_SHA256={result['provenance_sha256']}")
        print(f"DIRECT_MR_{tag}_VERTEX_COUNT={result['vertex_count']}")
        print(f"DIRECT_MR_{tag}_TRIANGLE_COUNT={result['triangle_count']}")
        print(f"DIRECT_MR_{tag}_PAYLOAD_BYTES={result['payload_bytes']}")
        print(f"DIRECT_MR_{tag}_DEGENERATE_TRIANGLE_COUNT={result['degenerate_triangle_count']}")
        print(f"DIRECT_MR_{tag}_DEGENERATE_TRIANGLE_FRACTION={float(result['degenerate_triangle_fraction']):.12f}")
        print("DIRECT_MR_" + tag + "_BOUNDS_LPS_MM=" + ",".join(f"{float(value):.3f}" for value in result["bounds_lps_mm"]))

    if preferred is None:
        print("MANUAL_PREFERRED_SAMPLE_ISOVALUE=NOT_RECORDED")
    else:
        print(f"MANUAL_PREFERRED_SAMPLE_ISOVALUE={preferred:.2f}")
        print("MANUAL_THRESHOLD_JUDGMENT=USER_SUPPLIED_SAMPLE_SPECIFIC")
    print("SOURCE_VOLUME=IMMUTABLE")
    print("GEOMETRY_CHAIN=PATIENT_LPS")
    print("DIRECT_MR_SEGMENTATION_REQUIRED=NO")
    print("DIRECT_MR_PAYLOADS_DISTINCT=PASS")
    print("DIRECT_MR_GEOMETRY_BUDGETS=PASS")
    print("DIRECT_MR_VISUAL_REVIEW=MANUAL_REQUIRED")
    print("DIRECT_CT_BACKWARD_SANITY=MANUAL_REQUIRED")
    print("MRI_INFERENCE=NOT_RUN")
    print("CLINICAL_VALIDATION=NOT_CLAIMED")
    print("PHASE6J_D45D_REAL_MRI_QUALIFICATION_OK=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
