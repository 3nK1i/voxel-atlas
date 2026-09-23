#!/usr/bin/env python3
"""Isolated MRI canonical NPY <-> NIfTI bridge; no inference or provider registration.

The pre-existing Phase 5B2 CT bridge is intentionally not imported or modified.
Only the local study-bound, canonical MR volume may be exported. A returned MR
mask must preserve input NIfTI geometry and the 50-class total_mr contract.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sys

SCHEMA_VERSION = 1
AXIS_ORDER = ["slice", "row", "column"]
MAX_MR_LABEL = 50
MAX_DESCRIPTOR_BYTES = 1024 * 1024


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_file(value: str, field: str) -> Path:
    path = Path(value)
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or path.parent.is_symlink()):
        raise ValueError(f"{field} is unavailable or unsafe")
    return path.resolve(strict=True)


def new_file(value: str, field: str) -> Path:
    path = Path(value)
    if (not path.is_absolute() or path.is_symlink() or path.exists()
            or path.parent.is_symlink() or not path.parent.is_dir()):
        raise ValueError(f"{field} is unavailable or unsafe")
    return path.resolve(strict=False)


def load_mri_descriptor(path: Path) -> dict[str, object]:
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_DESCRIPTOR_BYTES:
        raise ValueError("Canonical MR descriptor is invalid")
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict) or descriptor.get("ready") is not True:
        raise ValueError("Canonical MR volume is not ready")
    if descriptor.get("modality") != "MR":
        raise ValueError("MRI bridge accepts MR only")
    if descriptor.get("dtype") != "float32" or descriptor.get("axis_order") != AXIS_ORDER:
        raise ValueError("Canonical MR representation is unsupported")
    shape = descriptor.get("shape")
    if (not isinstance(shape, list) or len(shape) != 3
            or any(type(v) is not int or v <= 0 for v in shape)):
        raise ValueError("Canonical MR shape is invalid")
    affine = descriptor.get("array_index_to_patient_lps")
    if (not isinstance(affine, list) or len(affine) != 4
            or any(not isinstance(row, list) or len(row) != 4 or
                   any(type(v) not in (float, int) or not isfinite(v) for v in row)
                   for row in affine)
            or [float(v) for v in affine[3]] != [0., 0., 0., 1.]):
        raise ValueError("Canonical MR Patient-LPS geometry is invalid")
    return descriptor


def validate_mask_array(mask: object) -> tuple[list[int], int]:
    import numpy as np
    array = np.asarray(mask)
    if array.ndim != 3 or not np.issubdtype(array.dtype, np.number):
        raise ValueError("MRI segmentation mask is invalid")
    if not np.all(np.isfinite(array)):
        raise ValueError("MRI segmentation mask has non-finite labels")
    if not np.array_equal(array, np.rint(array)):
        raise ValueError("MRI segmentation mask has non-integer labels")
    if not np.all((array >= 0) & (array <= MAX_MR_LABEL)):
        raise ValueError("MRI segmentation mask labels are outside total_mr")
    labels = [int(label) for label in np.unique(array)]
    return labels, int(np.count_nonzero(array))


def export_mri(source_path: Path, descriptor_path: Path, output_path: Path) -> dict[str, object]:
    import nibabel as nib
    import numpy as np
    descriptor = load_mri_descriptor(descriptor_path)
    volume = np.load(source_path, mmap_mode="r", allow_pickle=False)
    shape = tuple(descriptor["shape"])
    if volume.ndim != 3 or volume.shape != shape or volume.dtype != np.dtype("float32"):
        raise ValueError("Canonical MR data and descriptor disagree")
    if not np.all(np.isfinite(volume)):
        raise ValueError("Canonical MR volume contains non-finite samples")
    lps = np.asarray(descriptor["array_index_to_patient_lps"], dtype=np.float64)
    if not np.isfinite(np.linalg.det(lps[:3, :3])) or abs(np.linalg.det(lps[:3, :3])) <= 1e-12:
        raise ValueError("Canonical MR Patient-LPS geometry is singular")
    ras = np.diag([-1., -1., 1., 1.]) @ lps
    image = nib.Nifti1Image(volume, ras)
    image.set_sform(ras, code=1)
    # The sform is authoritative; a qform cannot represent arbitrary shear.
    image.set_qform(ras, code=0)
    image.header.set_xyzt_units("mm")
    nib.save(image, output_path)
    if output_path.is_symlink() or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise ValueError("Canonical MR NIfTI export failed")
    return {
        "schema_version": SCHEMA_VERSION, "operation": "export", "task": "total_mr",
        "modality": "MR", "source_artifact_sha256": sha256_file(source_path),
        "source_descriptor_sha256": sha256(canonical_json(descriptor)).hexdigest(),
        "output_nifti_sha256": sha256_file(output_path), "shape": list(shape),
        "dtype": "float32", "axis_order": AXIS_ORDER,
        "array_index_to_patient_ras": ras.tolist(),
        "output_bytes": output_path.stat().st_size,
    }


def inspect_mri_mask(input_path: Path, mask_path: Path) -> dict[str, object]:
    import nibabel as nib
    import numpy as np
    if input_path.resolve(strict=True) == mask_path.resolve(strict=True):
        raise ValueError("MRI input and segmentation mask must be distinct")
    input_image = nib.load(input_path)
    mask_image = nib.load(mask_path)
    if (len(input_image.shape) != 3 or len(mask_image.shape) != 3
            or input_image.shape != mask_image.shape):
        raise ValueError("MRI segmentation shape does not match source")
    if not np.allclose(input_image.affine, mask_image.affine, rtol=0, atol=1e-5):
        raise ValueError("MRI segmentation Patient-RAS geometry changed")
    labels, nonzero = validate_mask_array(np.asanyarray(mask_image.dataobj))
    if mask_path.stat().st_size <= 0:
        raise ValueError("MRI segmentation mask is empty")
    return {
        "schema_version": SCHEMA_VERSION, "operation": "inspect", "task": "total_mr",
        "modality": "MR", "input_nifti_sha256": sha256_file(input_path),
        "mask_nifti_sha256": sha256_file(mask_path), "shape": list(input_image.shape),
        "affine_matches_input": True, "integer_labels": True,
        "minimum_label": labels[0], "maximum_label": labels[-1],
        "present_labels": labels, "nonzero_voxels": nonzero,
        "output_bytes": mask_path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VoxelAtlas isolated canonical MRI bridge")
    operations = parser.add_subparsers(dest="operation", required=True)
    exporting = operations.add_parser("export")
    exporting.add_argument("--source-npy", required=True)
    exporting.add_argument("--metadata-json", required=True)
    exporting.add_argument("--output-nifti", required=True)
    inspecting = operations.add_parser("inspect")
    inspecting.add_argument("--input-nifti", required=True)
    inspecting.add_argument("--mask-nifti", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "export":
            report = export_mri(existing_file(args.source_npy, "Canonical MR NPY"),
                                existing_file(args.metadata_json, "Canonical MR descriptor"),
                                new_file(args.output_nifti, "MRI NIfTI output"))
        else:
            report = inspect_mri_mask(existing_file(args.input_nifti, "MRI NIfTI input"),
                                      existing_file(args.mask_nifti, "MRI segmentation mask"))
    except Exception as exc:
        # Never expose input paths, patient details, or model stderr to the UI.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(canonical_json(report).decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
