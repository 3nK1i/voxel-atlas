#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from time import perf_counter

import numpy as np
from scipy.ndimage import find_objects, label as connected_components

STUDY_ID = re.compile(r"^[0-9a-f]{32}$")


def latest_manifest(data_dir: Path, requested: str | None) -> Path:
    studies = data_dir / "studies"
    if requested:
        value = requested.strip().lower()
        if STUDY_ID.fullmatch(value) is None:
            raise ValueError("study id is invalid")
        path = studies / value / "manifest.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("study manifest is unavailable")
        return path
    manifests = [item for item in studies.glob("*/manifest.json") if item.is_file() and not item.is_symlink()]
    if not manifests:
        raise ValueError("no stored study manifest is available")
    return max(manifests, key=lambda item: item.stat().st_mtime_ns)


def load_source(manifest_path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    descriptor = payload.get("volume")
    if not isinstance(descriptor, dict) or descriptor.get("ready") is not True:
        raise ValueError("canonical patient volume is not ready")
    if descriptor.get("artifact_path") != "derived/volume.npy":
        raise ValueError("canonical patient volume artifact contract is invalid")
    volume_path = manifest_path.parent / "derived" / "volume.npy"
    if volume_path.is_symlink() or not volume_path.is_file():
        raise ValueError("canonical patient volume artifact is unavailable")
    volume = np.load(volume_path, mmap_mode="r", allow_pickle=False)
    shape = tuple(int(item) for item in descriptor.get("shape", []))
    if volume.ndim != 3 or tuple(volume.shape) != shape or str(volume.dtype) != "float32":
        raise ValueError("canonical patient volume artifact is inconsistent")
    affine = np.asarray(descriptor.get("array_index_to_patient_lps"), dtype=np.float64)
    if affine.shape != (4, 4) or not np.all(np.isfinite(affine)):
        raise ValueError("Patient LPS affine is invalid")
    return volume, affine


def component_report(volume: np.ndarray, threshold: float, label_name: str, maximum: int) -> None:
    started = perf_counter()
    binary = np.asarray(volume >= np.float32(threshold), dtype=np.bool_)
    structure = np.ones((3, 3, 3), dtype=np.uint8)
    labels, count = connected_components(binary, structure=structure)
    counts = np.bincount(labels.ravel())
    objects = find_objects(labels)
    boundary_labels = set()
    for face in (labels[0], labels[-1], labels[:, 0], labels[:, -1], labels[:, :, 0], labels[:, :, -1]):
        boundary_labels.update(int(item) for item in np.unique(face) if int(item) != 0)
    ranking = np.argsort(counts[1:])[::-1] + 1 if len(counts) > 1 else np.asarray([], dtype=np.int64)
    total_foreground = int(binary.sum())
    elapsed_ms = (perf_counter() - started) * 1000.0
    print(f"{label_name}_THRESHOLD={threshold:.3f}")
    print(f"{label_name}_FOREGROUND_VOXELS={total_foreground}")
    print(f"{label_name}_COMPONENT_COUNT={int(count)}")
    print(f"{label_name}_ANALYSIS_MS={elapsed_ms:.3f}")
    print(f"{label_name}_COMPONENTS_BEGIN")
    for rank, component_id in enumerate(ranking[:maximum], 1):
        slc = objects[int(component_id) - 1]
        if slc is None:
            continue
        starts = tuple(int(axis.start or 0) for axis in slc)
        stops = tuple(int(axis.stop or 0) for axis in slc)
        extents = tuple(max(0, stop - start) for start, stop in zip(starts, stops))
        longest = max(extents) if extents else 0
        shortest = min(extents) if extents else 0
        flatness_ratio = float(shortest / longest) if longest > 0 else 0.0
        box_voxels = int(np.prod(extents, dtype=np.int64)) if all(extents) else 0
        voxels = int(counts[int(component_id)])
        fill_ratio = float(voxels / box_voxels) if box_voxels else 0.0
        fraction = float(voxels / total_foreground) if total_foreground else 0.0
        print(
            f"{label_name}_COMPONENT rank={rank} id={int(component_id)} voxels={voxels} "
            f"fraction={fraction:.8f} index_start={starts} index_stop={stops} extents={extents} "
            f"touches_boundary={'YES' if int(component_id) in boundary_labels else 'NO'} "
            f"flatness_ratio={flatness_ratio:.8f} fill_ratio={fill_ratio:.8f}"
        )
    print(f"{label_name}_COMPONENTS_END")
    del labels, binary, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only post-6F Direct-CT component diagnostic")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--study-id")
    parser.add_argument("--isovalue", type=float, default=300.0)
    parser.add_argument("--body-threshold", type=float, default=-500.0)
    parser.add_argument("--max-components", type=int, default=12)
    args = parser.parse_args()
    if args.max_components < 1 or args.max_components > 50:
        raise SystemExit("--max-components must be between 1 and 50")
    manifest = latest_manifest(args.data_dir.expanduser().resolve(), args.study_id)
    volume, _affine = load_source(manifest)
    print("===== POST-6F DIRECT-CT SURFACE DIAGNOSTIC =====")
    print(f"STUDY_ID={manifest.parent.name}")
    print("SOURCE=CANONICAL_VOLUME")
    print(f"SOURCE_SHAPE={'x'.join(str(int(item)) for item in volume.shape)}")
    print("SOURCE_UNITS=HU")
    print("CANONICAL_VOLUME_MUTATION=NO")
    component_report(volume, float(args.isovalue), "ISOVALUE", args.max_components)
    component_report(volume, float(args.body_threshold), "BODY_SUPPORT", args.max_components)
    print("ISOVALUE_COMPONENTS=REPORTED")
    print("BODY_SUPPORT_COMPONENTS=REPORTED")
    print("ARBITRARY_LARGEST_COMPONENT_REMOVAL=NOT_APPLIED")
    print("DIRECT_CT_CORRECTION_DECISION=REQUIRES_COMPONENT_EVIDENCE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
