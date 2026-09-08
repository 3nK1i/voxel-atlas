#!/usr/bin/env python3
"""Isolated NPY/NIfTI bridge for Phase 5B2; run only in the provider environment."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sys


SCHEMA_VERSION = 1
AXIS_ORDER = ["slice", "row", "column"]
MAX_LABEL = 117


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
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
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{field} must be an absolute non-symlink path")
    path = path.resolve(strict=False)
    if path.exists():
        raise ValueError(f"{field} must not already exist")
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError(f"{field} parent is unsafe")
    return path


def load_descriptor(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("canonical descriptor must be an object")
    if payload.get("ready") is not True:
        raise ValueError("canonical volume is not ready")
    if payload.get("modality") != "CT":
        raise ValueError("Phase 5B2 accepts CT only")
    if payload.get("dtype") != "float32" or payload.get("axis_order") != AXIS_ORDER:
        raise ValueError("canonical volume representation is unsupported")
    shape = payload.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
    ):
        raise ValueError("canonical volume shape is invalid")
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


def export_volume(source_path: Path, metadata_path: Path, output_path: Path) -> dict[str, object]:
    import nibabel as nib
    import numpy as np

    descriptor = load_descriptor(metadata_path)
    volume = np.load(source_path, mmap_mode="r", allow_pickle=False)
    expected_shape = tuple(int(item) for item in descriptor["shape"])
    if tuple(volume.shape) != expected_shape or str(volume.dtype) != "float32":
        raise ValueError("canonical array does not match its descriptor")
    lps_affine = np.asarray(descriptor["array_index_to_patient_lps"], dtype=np.float64)
    if abs(float(np.linalg.det(lps_affine[:3, :3]))) <= 1e-12:
        raise ValueError("canonical Patient LPS affine is singular")

    # NIfTI uses RAS world coordinates; VoxelAtlas canonical geometry is Patient LPS.
    lps_to_ras = np.diag([-1.0, -1.0, 1.0, 1.0])
    ras_affine = lps_to_ras @ lps_affine
    image = nib.Nifti1Image(volume, ras_affine)
    image.set_qform(ras_affine, code=1)
    image.set_sform(ras_affine, code=1)
    image.header.set_xyzt_units("mm")
    nib.save(image, output_path)
    if output_path.is_symlink() or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise ValueError("NIfTI export was not created")
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "export",
        "source_artifact_sha256": sha256_file(source_path),
        "source_descriptor_sha256": sha256(canonical_json(descriptor)).hexdigest(),
        "output_nifti_sha256": sha256_file(output_path),
        "shape": list(expected_shape),
        "dtype": "float32",
        "axis_order": AXIS_ORDER,
        "array_index_to_patient_ras": ras_affine.tolist(),
        "output_bytes": output_path.stat().st_size,
    }


def inspect_mask(input_path: Path, mask_path: Path) -> dict[str, object]:
    import nibabel as nib
    import numpy as np

    input_image = nib.load(input_path)
    mask_image = nib.load(mask_path)
    if len(input_image.shape) != 3 or tuple(input_image.shape) != tuple(mask_image.shape):
        raise ValueError("segmentation mask shape does not match input")
    affine_matches = bool(np.allclose(input_image.affine, mask_image.affine, rtol=0.0, atol=1e-5))
    if not affine_matches:
        raise ValueError("segmentation mask affine does not match input")
    mask = np.asanyarray(mask_image.dataobj)
    if not np.all(np.isfinite(mask)):
        raise ValueError("segmentation mask contains non-finite labels")
    rounded = np.rint(mask)
    integer_labels = bool(np.array_equal(mask, rounded))
    if not integer_labels:
        raise ValueError("segmentation mask contains non-integer labels")
    labels = [int(item) for item in np.unique(rounded)]
    minimum = labels[0]
    maximum = labels[-1]
    if minimum != 0 or maximum > MAX_LABEL:
        raise ValueError("segmentation mask labels are outside the total-task contract")
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "inspect",
        "input_nifti_sha256": sha256_file(input_path),
        "mask_nifti_sha256": sha256_file(mask_path),
        "shape": list(input_image.shape),
        "affine_matches_input": affine_matches,
        "integer_labels": integer_labels,
        "minimum_label": minimum,
        "maximum_label": maximum,
        "nonzero_voxels": int(np.count_nonzero(rounded)),
        "present_labels": labels,
        "output_bytes": mask_path.stat().st_size,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VoxelAtlas Phase 5B2 isolated NIfTI bridge")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    export_parser = subparsers.add_parser("export", help="Export canonical NPY to NIfTI RAS")
    export_parser.add_argument("--source-npy", required=True)
    export_parser.add_argument("--metadata-json", required=True)
    export_parser.add_argument("--output-nifti", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Validate a multilabel NIfTI mask")
    inspect_parser.add_argument("--input-nifti", required=True)
    inspect_parser.add_argument("--mask-nifti", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.operation == "export":
            report = export_volume(
                absolute_regular_file(args.source_npy, "source NPY"),
                absolute_regular_file(args.metadata_json, "metadata JSON"),
                absolute_output(args.output_nifti, "output NIfTI"),
            )
        else:
            report = inspect_mask(
                absolute_regular_file(args.input_nifti, "input NIfTI"),
                absolute_regular_file(args.mask_nifti, "mask NIfTI"),
            )
    except Exception as exc:  # The parent keeps worker details private.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
