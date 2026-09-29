from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6FEAnatomicalGroupExplodedPresentationTests(unittest.TestCase):
    def test_bounded_group_explosion_module_exists_and_is_display_only(self) -> None:
        path = ROOT / "web/js/segmentation-exploded-presentation.js"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        for token in (
            "MAX_ANATOMICAL_GROUP_EXPLODE_MM",
            "applyAnatomicalGroupExplosion",
            "resetAnatomicalGroupExplosion",
            "patientLpsOffsetToViewer",
            "explodedOffsetLpsMm",
        ):
            self.assertIn(token, text)
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "marching_cubes",
            "setAttribute(\"position\"",
            "setIndex(",
            "geometry.applyMatrix4",
            "/api/",
        ):
            self.assertNotIn(forbidden, text)

    def test_structure_panel_exposes_one_bounded_group_separation_control(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="segmentationStructureExplode"', html)
        self.assertIn('id="segmentationStructureExplodeValue"', html)
        self.assertIn("Explode anatomy", html)
        self.assertIn("applyAnatomicalGroupExplosion", panel)
        self.assertIn("segmentationStructureExplode", panel)
        self.assertIn("structure-explode-control", css)

    def test_segmentation_surface_viewer_applies_offsets_without_editing_geometry(self) -> None:
        viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(encoding="utf-8")
        helper = (ROOT / "web/js/reconstruction-surface-clipping.js").read_text(encoding="utf-8")

        self.assertIn("patientLpsOffsetToViewer", viewer)
        self.assertIn("item.mesh.position.set", viewer)
        self.assertIn("interaction.explodedOffsetLpsMm", viewer)
        self.assertIn("viewerOffset", helper)
        self.assertIn("descriptor.constant - normalDotOffset", helper)

    def test_cache_keys_and_phase_boundary_are_explicit(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("phase6f-e-r1", html)
        self.assertIn("phase6f-e-r1", app)

        doc = ROOT / "docs/phase_history/PHASE6F_E_ANATOMICAL_GROUP_EXPLODED_PRESENTATION.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        for token in (
            "Phase 6F-E",
            "anatomical group",
            "bounded",
            "display-only",
            "Patient LPS",
            "No geometry rebuild",
            "No geometry fetch",
            "Phase 6F-F",
            "Direct CT",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
