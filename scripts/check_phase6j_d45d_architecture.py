#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE_SHORT = "c688507"

QUALIFICATION_ONLY_ALLOWED_PATHS = {
    "docs/phase_history/PHASE6J_D45D_DIRECT_MRI_FINAL_ACCEPTANCE.md",
    "scripts/check_phase6j_b1_mri_workflow.mjs",
    "scripts/check_phase6j_b2b_mri_study_workflows.mjs",
    "scripts/check_phase6j_d45d_architecture.py",
    "scripts/qualify_phase6j_d45d_real_mri.py",
    "scripts/run_phase6j_d45d_checks.sh",
    "tests/test_phase6i_b2_existing_segmentation_mode.py",
    "tests/test_phase6j_d45d_direct_mri_acceptance.py",
}

PROTECTED_PRODUCTION_PREFIXES = (
    "backend/",
    "web/",
    "requirements/",
    "design/",
)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def changed_paths() -> set[str]:
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        changed.update(line for line in git(*args).splitlines() if line)
    return changed


def main() -> int:
    head = git("rev-parse", "--short", "HEAD")
    if head != EXPECTED_BASE_SHORT:
        raise SystemExit(f"D4.5D must start from {EXPECTED_BASE_SHORT}; current HEAD={head}")

    changed = changed_paths()
    if changed != QUALIFICATION_ONLY_ALLOWED_PATHS:
        unexpected = sorted(changed - QUALIFICATION_ONLY_ALLOWED_PATHS)
        missing = sorted(QUALIFICATION_ONLY_ALLOWED_PATHS - changed)
        raise SystemExit(
            "D4.5D must remain a eight-file qualification-only delta; "
            f"unexpected={unexpected}; missing={missing}"
        )
    if any(path.startswith(PROTECTED_PRODUCTION_PREFIXES) for path in changed):
        raise SystemExit("D4.5D changed protected production implementation")

    backend = text("backend/voxelatlas/volume_surfaces.py")
    app = text("web/js/app.js")
    viewer = text("web/js/volume-surface-viewer.js")
    index = text("web/index.html")
    css = text("web/css/styles.css")

    required_backend = (
        'DEFAULT_CT_BONE_ISOVALUE_HU = 300.0',
        'DEFAULT_MR_NORMALIZED_ISOVALUE = 0.50',
        'MRI_SURFACE_INTENSITY_UNITS = "normalized_signal"',
        'MRI_NORMALIZATION_LOW_PERCENTILE = 2.0',
        'MRI_NORMALIZATION_HIGH_PERCENTILE = 98.0',
        'MRI_PRESENTATION_GAUSSIAN_SIGMA_MM = 0.75',
        'MAX_VOLUME_SURFACE_VERTICES = 2_000_000',
        'MAX_VOLUME_SURFACE_TRIANGLES = 4_000_000',
        '"segmentation_required": False',
        '"coordinate_system": "patient_lps"',
    )
    for token in required_backend:
        if token not in backend:
            raise SystemExit(f"Qualified Direct MR/CT backend contract changed: {token}")

    required_ui = (
        'descriptor?.source_modality === "MR" ? "Direct MR" : "Direct CT"',
        '"Normalized MRI isovalue"',
        '"Relative signal after robust 2–98% normalization"',
        'volumeSurfaceRegionControl.hidden = true',
        'state.volumeSurface.descriptor?.source_modality === "CT"',
        'canPrepareAutomaticDirectVolumeSurface',
        'ensureAutomaticDirectVolumeSurface',
    )
    for token in required_ui:
        if token not in app:
            raise SystemExit(f"Qualified modality-aware Direct MR UI changed: {token}")

    if 'this.descriptor.surface_isovalue_range' not in viewer:
        raise SystemExit("Direct MR normalized-isovalue browser range binding changed")
    if 'this.descriptor?.source_modality !== "CT"' not in viewer:
        raise SystemExit("Direct CT region evidence guard changed")
    if '.volume-surface-region-control[hidden]' not in css or 'display: none !important;' not in css:
        raise SystemExit("MRI CT-only region-control hiding contract changed")
    panel = index.split('id="reconstructionPanel"', 1)[1].split('</section>', 1)[0]
    if 'data-help-reconstruction-mode' in panel:
        raise SystemExit("Volume/Surface/Combined question-mark help unexpectedly returned")

    print("PHASE6J_D45D_ARCHITECTURE=PASS")
    print(f"EXPECTED_BASE={EXPECTED_BASE_SHORT}")
    print("QUALIFICATION_ONLY_DELTA=YES")
    print("PRODUCTION_IMPLEMENTATION_CHANGED=NO")
    print("DIRECT_MR_DEFAULT_ISOVALUE=0.50")
    print("SAMPLE_MANUAL_PREFERRED_ISOVALUE=0.35")
    print("DIRECT_CT_DEFAULT_HU=300")
    print("PATIENT_LPS=PRESERVED")
    print("MRI_SEGMENTATION_DEPENDENCY=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
