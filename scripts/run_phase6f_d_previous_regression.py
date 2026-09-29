#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

CURRENT_PREFIXES = (
    "test_phase6f_d_per_structure_clipping_participation.",
    "test_phase6f_c_structure_transparency_robustness.",
    "test_phase6e_e_combined_mode_visual_balancing.",
    "test_phase6e_d_presentation_skull_cavity_polish.",
    "test_phase6e_c_fidelity_profile_qualification.",
    "test_phase6e_b_shared_lighting_material_foundation.",
    "test_phase6e_a_presentation_profile_architecture.",
    "test_phase6d2a_visualization_mode_controller.",
    "test_phase6d2b_volume_surface_transitions.",
    "test_phase6d2c_combined_visualization.",
    "test_phase6d2d_reset_study_error_closure.",
)
EXCLUDED_SUPERSEDED_ASSERTIONS = {
    "test_phase2a_workspace_migration.Phase2AWorkspaceMigrationTests.test_layer_contract_is_structural_without_faking_patient_anatomy",
    "test_phase2b_final_workspace_target.Phase2BFinalWorkspaceTargetTests.test_anatomical_layer_architecture_is_truthful_and_volume_only",
    "test_phase2b_final_workspace_target.Phase2BFinalWorkspaceTargetTests.test_workspace_matches_locked_v1_shell_structure",
    "test_phase3a_r2_final_viewer_micro_polish.Phase3AR2FinalViewerMicroPolishTests.test_zero_opacity_hides_the_volume_and_updates_the_ray_marcher",
    "test_phase3d_r2_final_selection_state.Phase3DR2FinalSelectionStateTests.test_full_volume_is_disabled_until_verified_texture_is_ready",
    "test_phase3d_r2_final_selection_state.Phase3DR2FinalSelectionStateTests.test_layer_buttons_expose_pressed_state",
    "test_phase4b_direct_volume_rendering_foundation.Phase4BDirectVolumeRenderingFrontendContractTests.test_frontend_qualifies_webgl2_without_enabling_unimplemented_volume_layer",
    "test_phase4c1_volume_texture_transport.Phase4C1VolumeTextureTransportTests.test_c1_transport_remains_separate_from_the_c2_ray_marcher",
    "test_phase4c2_true_volume_ray_marching.Phase4C2TrueVolumeRayMarchingTests.test_patient_lps_transform_and_truthful_layer_lifecycle_are_integrated",
    "test_phase4d1_volume_only_workspace.Phase4D1VolumeOnlyWorkspaceTests.test_full_volume_is_the_only_anatomical_layer",
    "test_phase4d1_volume_only_workspace.Phase4D1VolumeOnlyWorkspaceTests.test_volume_only_state_remains_truthful_until_gpu_rendering_is_ready",
    "test_phase4h3a_medical_projection_modes.Phase4H3AMedicalProjectionModesTests.test_primary_panel_exposes_four_truthful_rendering_modes",
    "test_phase4h3b_slice_and_thick_slab.Phase4H3BSliceAndThickSlabTests.test_canonical_volume_and_safety_contracts_remain_unchanged",
    "test_phase4h4_dual_sided_patient_lps_clipping.Phase4H4DualSidedPatientLpsClippingTests.test_all_volume_modes_reuse_the_same_clipped_resident_texture",
    "test_phase4h5_mpr_clipping_visualization.MprClippingVisualizationTests.test_readable_clipping_typography",
    "test_phase4h6_qualification.RenderingQualificationTests.test_compact_readable_clipping_labels",
    "test_phase6c_polished_multi_structure_presentation.Phase6CPolishedMultiStructurePresentationTests.test_phase6c_roadmap_boundary_remains_explicit",
    "test_phase6d1_volume_derived_surfaces.Phase6D1VolumeDerivedSurfaceTests.test_frontend_requires_explicit_build_and_does_not_enable_phase6d2_modes",
    "test_phase6d1_surface_only_preview_correction.Phase6D1SurfaceOnlyPreviewCorrectionTests.test_direct_volume_visibility_excludes_active_volume_surface_preview",
    "test_phase6d1_surface_only_preview_correction.Phase6D1SurfaceOnlyPreviewCorrectionTests.test_successful_surface_build_hides_volume_only_after_build_resolves",
    "test_phase6d1_surface_only_preview_correction.Phase6D1SurfaceOnlyPreviewCorrectionTests.test_remove_surface_restores_direct_volume_visibility_policy",
    "test_phase6d1_surface_only_preview_correction.Phase6D1SurfaceOnlyPreviewCorrectionTests.test_phase6d1_stays_surface_only_preview_not_phase6d2_modes",
    "test_phase6f_a_structure_interaction_state.Phase6FAStructureInteractionStateTests.test_phase6f_a_foundation_keeps_later_interaction_features_out_of_scope",
    "test_phase6f_b_non_destructive_visibility_isolation.Phase6FBNonDestructiveVisibilityIsolationTests.test_6fb_does_not_enable_later_interaction_features",
}


def iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def main() -> int:
    discovered = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT / "tests")
    )
    selected = unittest.TestSuite()
    current = 0
    superseded = []
    for test in iter_tests(discovered):
        if test.id().startswith(CURRENT_PREFIXES):
            current += 1
        elif test.id() in EXCLUDED_SUPERSEDED_ASSERTIONS:
            superseded.append(test.id())
        else:
            selected.addTest(test)
    missing = sorted(EXCLUDED_SUPERSEDED_ASSERTIONS.difference(superseded))
    if missing or current == 0:
        print("PHASE6F_D_PREVIOUS_REGRESSION=FAIL")
        print("MISSING_EXCLUSIONS=" + ",".join(missing))
        return 1
    result = unittest.TextTestRunner(verbosity=1).run(selected)
    print(f"CURRENT_PHASE_TESTS_EXCLUDED={current}")
    print(f"EXPLICIT_SUPERSEDED_ASSERTIONS={len(superseded)}")
    if result.wasSuccessful():
        print("PHASE6F_D_PREVIOUS_REGRESSION=PASS")
        return 0
    print("PHASE6F_D_PREVIOUS_REGRESSION=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
