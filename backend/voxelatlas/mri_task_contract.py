"""6J-B1: pinned MRI task identity and source-level label contract (no inference).

Source: installed TotalSegmentator 2.18.0, map_to_binary.py ``total_mr``,
inspected 2026-09-23.  This catalog alone does not qualify weights, GPU, or
MRI sequence suitability; those require separate provider qualification.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

MRI_TASK_ID = "total_mr"
MRI_TASK_MODALITY = "MR"
MRI_TASK_CLASS_COUNT = 50
# Fingerprint of the installed source's AST dictionary segment, not a hash of
# this Python module or proof of installed runtime/weights at execution time.
MRI_TASK_SOURCE_MAPPING_SHA256 = (
    "63226e21df16918303452b90fb3f76a7640c5d5f7974b340cf942067bbfb28c7"
)

TOTAL_SEGMENTATOR_MRI_STRUCTURES: dict[int, str] = {
    1: "spleen",
    2: "kidney_right",
    3: "kidney_left",
    4: "gallbladder",
    5: "liver",
    6: "stomach",
    7: "pancreas",
    8: "adrenal_gland_right",
    9: "adrenal_gland_left",
    10: "lung_left",
    11: "lung_right",
    12: "esophagus",
    13: "small_bowel",
    14: "duodenum",
    15: "colon",
    16: "urinary_bladder",
    17: "prostate",
    18: "sacrum",
    19: "vertebrae",
    20: "intervertebral_discs",
    21: "spinal_cord",
    22: "heart",
    23: "aorta",
    24: "inferior_vena_cava",
    25: "portal_vein_and_splenic_vein",
    26: "iliac_artery_left",
    27: "iliac_artery_right",
    28: "iliac_vena_left",
    29: "iliac_vena_right",
    30: "humerus_left",
    31: "humerus_right",
    32: "scapula_left",
    33: "scapula_right",
    34: "clavicula_left",
    35: "clavicula_right",
    36: "femur_left",
    37: "femur_right",
    38: "hip_left",
    39: "hip_right",
    40: "gluteus_maximus_left",
    41: "gluteus_maximus_right",
    42: "gluteus_medius_left",
    43: "gluteus_medius_right",
    44: "gluteus_minimus_left",
    45: "gluteus_minimus_right",
    46: "autochthon_left",
    47: "autochthon_right",
    48: "iliopsoas_left",
    49: "iliopsoas_right",
    50: "brain",
}


def model_for_source_modality(*, provider_id: str, default_model_id: str, modality: str) -> str:
    """Keep the qualified CT model untouched; route MR to an independent model.

    Only the existing TotalSegmentator ``total`` workflow is specialized.
    Any other provider retains its explicitly configured model identity.
    """
    if provider_id == "totalsegmentator" and default_model_id == "total" and modality == "MR":
        return MRI_TASK_ID
    return default_model_id


def qualify_mri_canonical_descriptor(descriptor: Mapping[str, object]) -> tuple[bool, str]:
    """Qualification of *canonical image representation*, not MR sequence/model fitness.

    Called on the immutable descriptor from the normal DICOM ingestion path;
    it does not read source DICOM, patient metadata, or neural model assets.
    """
    if descriptor.get("ready") is not True or descriptor.get("modality") != MRI_TASK_MODALITY:
        return False, "A ready canonical MR volume is required"
    if descriptor.get("dtype") != "float32" or descriptor.get("axis_order") != ["slice", "row", "column"]:
        return False, "MRI canonical volume format is not supported"
    shape = descriptor.get("shape")
    if (not isinstance(shape, list) or len(shape) != 3
        or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in shape)):
        return False, "MRI canonical volume shape is invalid"
    affine = descriptor.get("array_index_to_patient_lps")
    if (not isinstance(affine, list) or len(affine) != 4
        or any(not isinstance(row, list) or len(row) != 4 for row in affine)):
        return False, "MRI canonical Patient-LPS geometry is invalid"
    for row in affine:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False, "MRI canonical Patient-LPS geometry is invalid"
            try:
                finite = isfinite(value)
            except (OverflowError, ValueError):
                finite = False
            if not finite:
                return False, "MRI canonical Patient-LPS geometry is invalid"
    if affine[3] != [0, 0, 0, 1]:
        return False, "MRI canonical Patient-LPS geometry is invalid"
    # Affine must be non-singular. No NumPy dependency in the lightweight app.
    a, b, c = (affine[index][:3] for index in range(3))
    det = (a[0] * (b[1] * c[2] - b[2] * c[1])
           - a[1] * (b[0] * c[2] - b[2] * c[0])
           + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if not isfinite(det) or abs(det) <= 1e-12:
        return False, "MRI canonical Patient-LPS geometry is singular"
    return True, "MRI canonical volume representation is eligible for provider qualification"
