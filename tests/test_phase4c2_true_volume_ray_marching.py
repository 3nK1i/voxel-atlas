from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase4C2TrueVolumeRayMarchingTests(unittest.TestCase):
    def test_renderer_ray_marches_verified_patient_voxels(self) -> None:
        renderer = (ROOT / "web/js/patient-volume-ray-marcher.js").read_text(
            encoding="utf-8"
        )

        for marker in (
            "uniform highp sampler3D uVolume",
            "intersectUnitBox",
            "decodeMedicalIntensity",
            "texture(uVolume, textureCoordinate)",
            "sampleMedicalTransfer",
            "uTransferIntensities",
            "uTransferOpacities",
            "uTransferColors",
            "accumulated.rgb += remaining * sampleAlpha * sampleColor",
            "accumulated.a += remaining * sampleAlpha",
            "if (accumulated.a >= 0.98)",
            "THREE.GLSL3",
            "THREE.BackSide",
            "THREE.NearestFilter",
            "premultipliedAlpha: true",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, renderer)

        self.assertNotIn("marchingCubes", renderer)
        self.assertNotIn("isocontour", renderer.lower())

    def test_patient_lps_transform_and_truthful_layer_lifecycle_are_integrated(self) -> None:
        renderer = (ROOT / "web/js/patient-volume-ray-marcher.js").read_text(
            encoding="utf-8"
        )
        app_js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")

        for marker in (
            "texture_coordinate_to_patient_lps",
            "PATIENT_LPS_TO_VIEWER",
            "PatientVolumeRayMarcher",
            "volumeRayMarcher.create",
            "setVolumeAvailability(true)",
            "applyVolumeVisibility()",
            "volumeRayMarcher.dispose()",
            "renderer.compileAsync(compileScene, camera)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, renderer + app_js)

        self.assertIn('data-layer="volume" disabled', html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4f', html)
        self.assertIn(
            'from "./patient-volume-ray-marcher.js?v=phase4f"',
            app_js,
        )
        self.assertIn("True patient voxel volume active.", app_js)

    def test_c2_preserves_deferred_medical_features_and_mpr_fallback(self) -> None:
        app_js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        documentation = (
            ROOT / "docs/phase_history/PHASE4C2_TRUE_PATIENT_VOLUME_RAY_MARCHING.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Synchronized MPR remains available.", app_js)
        self.assertIn("Phase 4D", documentation)
        self.assertIn("Phase 4E", documentation)
        self.assertIn("No segmentation", documentation)

    def test_compact_c2_validation_entrypoint_is_present(self) -> None:
        self.assertTrue((ROOT / "scripts/run_phase4c2_checks.sh").is_file())
        self.assertTrue((ROOT / "scripts/check_phase4c2_volume_ray_marcher.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
