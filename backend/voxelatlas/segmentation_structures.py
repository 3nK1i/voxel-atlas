from __future__ import annotations

from collections.abc import Iterable, Mapping
import re


STRUCTURE_CATALOG_SCHEMA_VERSION = 1
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


# TotalSegmentator's public ``total`` task taxonomy.  The numeric contract is
# pinned by Phase 5B and intentionally lives in the lightweight application
# environment instead of importing the heavy provider runtime.
# Source: wasserth/TotalSegmentator, totalsegmentator/map_to_binary.py.
TOTAL_SEGMENTATOR_TOTAL_STRUCTURES: dict[int, str] = {
    1: "spleen",
    2: "kidney_right",
    3: "kidney_left",
    4: "gallbladder",
    5: "liver",
    6: "stomach",
    7: "pancreas",
    8: "adrenal_gland_right",
    9: "adrenal_gland_left",
    10: "lung_upper_lobe_left",
    11: "lung_lower_lobe_left",
    12: "lung_upper_lobe_right",
    13: "lung_middle_lobe_right",
    14: "lung_lower_lobe_right",
    15: "esophagus",
    16: "trachea",
    17: "thyroid_gland",
    18: "small_bowel",
    19: "duodenum",
    20: "colon",
    21: "urinary_bladder",
    22: "prostate",
    23: "kidney_cyst_left",
    24: "kidney_cyst_right",
    25: "sacrum",
    26: "vertebrae_S1",
    27: "vertebrae_L5",
    28: "vertebrae_L4",
    29: "vertebrae_L3",
    30: "vertebrae_L2",
    31: "vertebrae_L1",
    32: "vertebrae_T12",
    33: "vertebrae_T11",
    34: "vertebrae_T10",
    35: "vertebrae_T9",
    36: "vertebrae_T8",
    37: "vertebrae_T7",
    38: "vertebrae_T6",
    39: "vertebrae_T5",
    40: "vertebrae_T4",
    41: "vertebrae_T3",
    42: "vertebrae_T2",
    43: "vertebrae_T1",
    44: "vertebrae_C7",
    45: "vertebrae_C6",
    46: "vertebrae_C5",
    47: "vertebrae_C4",
    48: "vertebrae_C3",
    49: "vertebrae_C2",
    50: "vertebrae_C1",
    51: "heart",
    52: "aorta",
    53: "pulmonary_vein",
    54: "brachiocephalic_trunk",
    55: "subclavian_artery_right",
    56: "subclavian_artery_left",
    57: "common_carotid_artery_right",
    58: "common_carotid_artery_left",
    59: "brachiocephalic_vein_left",
    60: "brachiocephalic_vein_right",
    61: "atrial_appendage_left",
    62: "superior_vena_cava",
    63: "inferior_vena_cava",
    64: "portal_vein_and_splenic_vein",
    65: "iliac_artery_left",
    66: "iliac_artery_right",
    67: "iliac_vena_left",
    68: "iliac_vena_right",
    69: "humerus_left",
    70: "humerus_right",
    71: "scapula_left",
    72: "scapula_right",
    73: "clavicula_left",
    74: "clavicula_right",
    75: "femur_left",
    76: "femur_right",
    77: "hip_left",
    78: "hip_right",
    79: "spinal_cord",
    80: "gluteus_maximus_left",
    81: "gluteus_maximus_right",
    82: "gluteus_medius_left",
    83: "gluteus_medius_right",
    84: "gluteus_minimus_left",
    85: "gluteus_minimus_right",
    86: "autochthon_left",
    87: "autochthon_right",
    88: "iliopsoas_left",
    89: "iliopsoas_right",
    90: "brain",
    91: "skull",
    92: "rib_left_1",
    93: "rib_left_2",
    94: "rib_left_3",
    95: "rib_left_4",
    96: "rib_left_5",
    97: "rib_left_6",
    98: "rib_left_7",
    99: "rib_left_8",
    100: "rib_left_9",
    101: "rib_left_10",
    102: "rib_left_11",
    103: "rib_left_12",
    104: "rib_right_1",
    105: "rib_right_2",
    106: "rib_right_3",
    107: "rib_right_4",
    108: "rib_right_5",
    109: "rib_right_6",
    110: "rib_right_7",
    111: "rib_right_8",
    112: "rib_right_9",
    113: "rib_right_10",
    114: "rib_right_11",
    115: "rib_right_12",
    116: "sternum",
    117: "costal_cartilages",
}


_GROUPS = (
    ("organs", "Organs"),
    ("respiratory", "Respiratory"),
    ("spine", "Spine"),
    ("cardiovascular", "Cardiovascular"),
    ("skeletal", "Skeletal"),
    ("nervous_system", "Nervous system"),
    ("muscles", "Muscles"),
    ("other", "Other"),
)
_GROUP_NAMES = dict(_GROUPS)


def _group_for_total_label(label_id: int) -> str:
    if 10 <= label_id <= 14 or label_id == 16:
        return "respiratory"
    if 25 <= label_id <= 50:
        return "spine"
    if 51 <= label_id <= 68:
        return "cardiovascular"
    if 69 <= label_id <= 78 or 91 <= label_id <= 117:
        return "skeletal"
    if label_id in (79, 90):
        return "nervous_system"
    if 80 <= label_id <= 89:
        return "muscles"
    if 1 <= label_id <= 24:
        return "organs"
    return "other"


def _display_name(identifier: str) -> str:
    tokens = identifier.split("_")
    side = next((token for token in tokens if token in {"left", "right"}), None)
    if side is not None:
        tokens.remove(side)
    rendered: list[str] = []
    for token in tokens:
        if len(token) >= 2 and token[0] in {"C", "L", "S", "T"} and token[1:].isdigit():
            rendered.append(token)
        elif token.isdigit():
            rendered.append(token)
        elif token == "vertebrae":
            rendered.append("Vertebra")
        elif token == "clavicula":
            rendered.append("Clavicle")
        elif token == "and":
            rendered.append("and")
        else:
            rendered.append(token.capitalize())
    if side is not None:
        rendered.insert(0, side.capitalize())
    return " ".join(rendered)


def build_structure_catalog(
    *,
    provider_id: str,
    model_id: str,
    present_labels: Iterable[int],
    palette: Mapping[int, str],
) -> dict[str, object]:
    """Build a provider-neutral presentation catalog for labels in one map."""
    labels = list(present_labels)
    if (
        labels != sorted(set(labels))
        or any(isinstance(label, bool) or not isinstance(label, int) or label <= 0 for label in labels)
    ):
        raise ValueError("Present segmentation labels are invalid")

    total_contract = provider_id == "totalsegmentator" and model_id == "total"
    structures: list[dict[str, object]] = []
    group_counts: dict[str, int] = {}
    for label_id in labels:
        color = palette.get(label_id)
        if not isinstance(color, str) or _HEX_COLOR.fullmatch(color) is None:
            raise ValueError("Segmentation structure palette is incomplete")
        if total_contract:
            name = TOTAL_SEGMENTATOR_TOTAL_STRUCTURES.get(label_id)
            if name is None:
                raise ValueError("TotalSegmentator label is outside the total task contract")
            group_id = _group_for_total_label(label_id)
        else:
            name = f"label_{label_id}"
            group_id = "other"
        group_counts[group_id] = group_counts.get(group_id, 0) + 1
        structures.append(
            {
                "label_id": label_id,
                "name": name,
                "display_name": _display_name(name),
                "group_id": group_id,
                "group_name": _GROUP_NAMES[group_id],
                "color_hex": color.lower(),
                "default_visible": True,
                "default_opacity": 1.0,
            }
        )

    groups = [
        {
            "group_id": group_id,
            "display_name": display_name,
            "structure_count": group_counts[group_id],
        }
        for group_id, display_name in _GROUPS
        if group_counts.get(group_id, 0) > 0
    ]
    return {
        "schema_version": STRUCTURE_CATALOG_SCHEMA_VERSION,
        "provider_id": provider_id,
        "model_id": model_id,
        "structure_count": len(structures),
        "groups": groups,
        "structures": structures,
    }
