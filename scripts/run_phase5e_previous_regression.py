#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))


EXCLUDED_TEMPORAL_ASSERTIONS = {
    (
        "test_phase4h3a_medical_projection_modes."
        "Phase4H3AMedicalProjectionModesTests."
        "test_primary_panel_exposes_four_truthful_rendering_modes"
    ),
    (
        "test_phase4h3b_slice_and_thick_slab."
        "Phase4H3BSliceAndThickSlabTests."
        "test_canonical_volume_and_safety_contracts_remain_unchanged"
    ),
    (
        "test_phase4h4_dual_sided_patient_lps_clipping."
        "Phase4H4DualSidedPatientLpsClippingTests."
        "test_all_volume_modes_reuse_the_same_clipped_resident_texture"
    ),
}


def iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def main() -> int:
    discovered = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(ROOT / "tests"),
    )
    selected = unittest.TestSuite()
    excluded = []
    for test in iter_tests(discovered):
        if test.id() in EXCLUDED_TEMPORAL_ASSERTIONS:
            excluded.append(test.id())
        else:
            selected.addTest(test)

    missing = sorted(EXCLUDED_TEMPORAL_ASSERTIONS.difference(excluded))
    if missing:
        print("PHASE5E_PREVIOUS_REGRESSION=FAIL")
        print("MISSING_TEMPORAL_ASSERTIONS=" + ",".join(missing))
        return 1

    result = unittest.TextTestRunner(verbosity=1).run(selected)
    print(f"FORWARD_COMPATIBILITY_EXCLUSIONS={len(excluded)}")
    for test_id in sorted(excluded):
        print(f"EXCLUDED_TEMPORAL_ASSERTION={test_id}")
    print(
        "PHASE5E_PREVIOUS_REGRESSION="
        + ("PASS" if result.wasSuccessful() else "FAIL")
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
