from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase6CPolishedMultiStructurePresentationTests(unittest.TestCase):
    def test_structure_presentation_tracks_independent_3d_surface_visibility(self) -> None:
        module = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
        self.assertIn("surfaceVisible", module)
        self.assertIn("activateSurfaceForStructure", module)
        self.assertIn("structure.surfaceVisible = visibility.checked", module)
        self.assertIn("structure.surfaceVisible = visible", module)

    def test_surface_layer_is_multi_resident_and_uses_polished_materials(self) -> None:
        module = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        self.assertIn("this.items = new Map()", module)
        self.assertIn("MAX_CONCURRENT_SURFACE_LOADS", module)
        self.assertIn("MeshStandardMaterial", module)
        self.assertIn("roughness", module)
        self.assertIn("metalness", module)
        self.assertIn("surfaceVisible", module)
        self.assertNotIn("this.current = null", module)
        self.assertNotIn("MeshPhongMaterial", module)

    def test_phase6c_ui_copy_is_multi_structure_and_cache_identity_advances(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("3D Segmentation Surfaces", index)
        self.assertIn("Patient LPS refined surfaces", index)
        self.assertIn("polished multi-structure presentation", index)
        self.assertIn("phase6a-r1-phase6b-r1-phase6c-r2", app)
        self.assertIn("phase6a-r1-phase6b-r1-phase6c-r2", index)
        self.assertIn("phase6c-r2", index)

    def test_phase6c_surface_building_feedback_is_explicit_and_real(self) -> None:
        viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        structures = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        self.assertIn("_surfaceStatusSnapshot", viewer)
        self.assertIn('return "building"', viewer)
        self.assertIn('return "queued"', viewer)
        self.assertIn("Building ${selected.displayName} surface…", viewer)
        self.assertIn("setSurfaceStatusSnapshot", structures)
        self.assertIn("structure-surface-state", structures)
        self.assertIn('data-surface-state="building"', css)
        self.assertIn("segmentation-surface-spin", css)
        self.assertIn('aria-live', app)
        self.assertNotIn("% complete", viewer.lower())

    def test_phase6c_build_feedback_does_not_change_surface_generation_contract(self) -> None:
        viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        self.assertIn("MAX_CONCURRENT_SURFACE_LOADS = 2", viewer)
        self.assertIn('quality: requestedQuality', viewer)
        self.assertIn('requestedQuality === "refined"', viewer)
        self.assertNotIn("EventSource", viewer)
        self.assertNotIn("WebSocket", viewer)

    def test_phase6c_adds_presentation_lighting_without_geometry_mutation(self) -> None:
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        self.assertIn("segmentationSurfaceFillLight", app)
        self.assertIn("segmentationSurfaceRimLight", app)
        lowered = viewer.lower()
        self.assertNotIn("smooth_bounded", lowered)
        self.assertNotIn("cluster_candidate", lowered)
        self.assertNotIn("marching_cubes", lowered)

    def test_phase6c_roadmap_boundary_remains_explicit(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "web/js/segmentation-surface-viewer.js",
                ROOT / "web/js/segmentation-structure-panel.js",
                ROOT / "web/js/app.js",
                ROOT / "web/index.html",
            )
        ).lower()
        for forbidden in (
            "start segmentation",
            "volume-derived surface",
            "custom hu",
            "presentation profile",
            "fidelity profile",
            "exploded view",
            "export stl",
            "export obj",
            "hausdorff",
        ):
            self.assertNotIn(forbidden, combined)
        self.assertNotIn("clinical-grade", combined)
        self.assertNotIn("diagnostic accuracy", combined)


if __name__ == "__main__":
    unittest.main()
