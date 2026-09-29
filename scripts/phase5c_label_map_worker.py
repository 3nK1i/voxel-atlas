#!/usr/bin/env python3
"""Isolated NIfTI-to-canonical-label-map worker for VoxelAtlas Phase 5C."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import sys


SCHEMA_VERSION = 1
AXIS_ORDER = ["slice", "row", "column"]
LPS_TO_RAS = (-1.0, -1.0, 1.0, 1.0)
NIFTI_GEOMETRY_ATOL_MM = 1e-4


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_regular_file(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{field} must be an absolute regular file")
    return path.resolve(strict=True)


def absolute_output(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.exists():
        raise ValueError(f"{field} must be a new absolute non-symlink path")
    resolved = path.resolve(strict=False)
    if resolved.parent.is_symlink() or not resolved.parent.is_dir():
        raise ValueError(f"{field} parent is unsafe")
    return resolved


def load_source_descriptor(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("ready") is not True:
        raise ValueError("canonical source descriptor is invalid")
    shape = payload.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
    ):
        raise ValueError("canonical source shape is invalid")
    if payload.get("axis_order") != AXIS_ORDER:
        raise ValueError("canonical source axis order is unsupported")
    if not isinstance(payload.get("dtype"), str) or not payload["dtype"]:
        raise ValueError("canonical source dtype is invalid")
    affine = payload.get("array_index_to_patient_lps")
    if not isinstance(affine, list) or len(affine) != 4:
        raise ValueError("canonical Patient LPS affine is invalid")
    for row in affine:
        if (
            not isinstance(row, list)
            or len(row) != 4
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not isfinite(float(item))
                for item in row
            )
        ):
            raise ValueError("canonical Patient LPS affine is invalid")
    if [float(item) for item in affine[3]] != [0.0, 0.0, 0.0, 1.0]:
        raise ValueError("canonical Patient LPS affine is invalid")
    return payload


def canonicalize_label_map(
    *,
    source_npy: Path,
    source_json: Path,
    mask_nifti: Path,
    output_npy: Path,
    maximum_label: int,
) -> dict[str, object]:
    import nibabel as nib
    import numpy as np

    descriptor = load_source_descriptor(source_json)
    expected_shape = tuple(int(item) for item in descriptor["shape"])
    source = np.load(source_npy, mmap_mode="r", allow_pickle=False)
    if tuple(source.shape) != expected_shape or str(source.dtype) != descriptor["dtype"]:
        raise ValueError("canonical source array changed")

    source_affine = np.asarray(
        descriptor["array_index_to_patient_lps"], dtype=np.float64
    )
    if abs(float(np.linalg.det(source_affine[:3, :3]))) <= 1e-12:
        raise ValueError("canonical Patient LPS affine is singular")

    mask_image = nib.load(mask_nifti)
    if len(mask_image.shape) != 3 or tuple(mask_image.shape) != expected_shape:
        raise ValueError("provider mask shape does not match canonical source")
    ras_to_lps = np.diag(LPS_TO_RAS)
    model_affine_lps = ras_to_lps @ np.asarray(mask_image.affine, dtype=np.float64)
    if not np.all(np.isfinite(model_affine_lps)):
        raise ValueError("provider mask affine is invalid")
    if not np.allclose(model_affine_lps[3], [0.0, 0.0, 0.0, 1.0], atol=1e-8):
        raise ValueError("provider mask affine is invalid")
    if abs(float(np.linalg.det(model_affine_lps[:3, :3]))) <= 1e-12:
        raise ValueError("provider mask affine is singular")

    source_to_model = np.linalg.inv(model_affine_lps) @ source_affine
    model_to_source = np.linalg.inv(source_affine) @ model_affine_lps
    if not np.allclose(
        model_affine_lps,
        source_affine,
        rtol=0.0,
        atol=NIFTI_GEOMETRY_ATOL_MM,
    ):
        raise ValueError("provider mask is not on the canonical Patient LPS grid")
    if not np.allclose(source_to_model, np.eye(4), rtol=0.0, atol=1e-5):
        raise ValueError("provider mask index transform is not identity")

    mask = np.asanyarray(mask_image.dataobj)
    if np.issubdtype(mask.dtype, np.floating):
        if not np.all(np.isfinite(mask)):
            raise ValueError("provider mask contains non-finite labels")
        rounded = np.rint(mask)
        if not np.array_equal(mask, rounded):
            raise ValueError("provider mask contains non-integer labels")
    elif np.issubdtype(mask.dtype, np.integer):
        rounded = mask
    else:
        raise ValueError("provider mask dtype is unsupported")
    labels = [int(item) for item in np.unique(rounded)]
    if (
        not labels
        or labels[0] != 0
        or labels[-1] > maximum_label
        or labels[0] < 0
    ):
        raise ValueError("provider mask labels are outside the model contract")

    canonical = np.asarray(rounded, dtype=np.uint16)
    with output_npy.open("xb") as handle:
        np.save(handle, canonical, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(output_npy, 0o600)
    if output_npy.is_symlink() or not output_npy.is_file():
        raise ValueError("canonical label-map output was not created")

    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "canonicalize_label_map",
        "source_artifact_sha256": sha256_file(source_npy),
        "source_descriptor_sha256": sha256(canonical_json(descriptor)).hexdigest(),
        "provider_mask_sha256": sha256_file(mask_nifti),
        "canonical_label_map_sha256": sha256_file(output_npy),
        "canonical_label_map_bytes": output_npy.stat().st_size,
        "shape": list(expected_shape),
        "dtype": "uint16",
        "axis_order": AXIS_ORDER,
        "coordinate_system": "patient_lps",
        "length_units": "mm",
        "array_index_to_patient_lps": source_affine.tolist(),
        "model_index_to_patient_lps": model_affine_lps.tolist(),
        "source_to_model_index": source_to_model.tolist(),
        "model_to_source_index": model_to_source.tolist(),
        "resampled": False,
        "interpolation": "none",
        "minimum_label": labels[0],
        "maximum_label": labels[-1],
        "present_labels": labels,
        "nonzero_voxels": int(np.count_nonzero(canonical)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonicalize one qualified segmentation mask in Patient LPS space"
    )
    parser.add_argument("--source-npy", required=True)
    parser.add_argument("--source-json", required=True)
    parser.add_argument("--mask-nifti", required=True)
    parser.add_argument("--output-npy", required=True)
    parser.add_argument("--maximum-label", required=True, type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.maximum_label <= 0 or args.maximum_label > 65535:
        print(json.dumps({"status": "failed", "error_type": "ValueError"}))
        return 1
    try:
        report = canonicalize_label_map(
            source_npy=absolute_regular_file(args.source_npy, "source NPY"),
            source_json=absolute_regular_file(args.source_json, "source JSON"),
            mask_nifti=absolute_regular_file(args.mask_nifti, "provider mask NIfTI"),
            output_npy=absolute_output(args.output_npy, "output NPY"),
            maximum_label=args.maximum_label,
        )
    except Exception as exc:  # Parent process keeps worker diagnostics private.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
