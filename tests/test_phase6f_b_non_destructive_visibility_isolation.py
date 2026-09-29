from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase6FBNonDestructiveVisibilityIsolationTests(unittest.TestCase):
    def test_interaction_module_owns_isolate_and_restore_transitions(self) -> None:
        module = (ROOT / "web/js/segmentation-structure-interaction.js").read_text(
            encoding="utf-8"
        )
        for token in (
            "activateStructureIsolation",
            "restoreStructureIsolation",
            "isolatedLabelId",
            "effectiveVisible",
            "effectiveSurfaceVisible",
        ):
            self.assertIn(token, module)
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "/api/",
            "marching_cubes",
            "geometry.dispose",
        ):
            self.assertNotIn(forbidden, module)

    def test_panel_wires_non_destructive_isolate_restore(self) -> None:
        panel = (ROOT / "web/js/segmentation-structure-panel.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("activateStructureIsolation", panel)
        self.assertIn("restoreStructureIsolation", panel)
        self.assertIn('action === "restore-isolation"', panel)
        self.assertIn("segmentationStructureRestoreIsolation", panel)
        self.assertNotIn("structure.visible = isolated", panel)
        self.assertNotIn("structure.surfaceVisible = isolated", panel)

    def test_overlay_uses_effective_visibility_without_mutating_labels(self) -> None:
        overlay = (ROOT / "web/js/segmentation-overlay.js").read_text(encoding="utf-8")
        self.assertIn("resolveStructureInteraction", overlay)
        self.assertIn("effectiveVisible", overlay)
        self.assertNotIn("presentation.interaction.isolatedLabelId =", overlay)

    def test_surface_viewer_gates_resident_meshes_without_changing_requests(self) -> None:
        viewer = (ROOT / "web/js/segmentation-surface-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("resolveStructureInteraction", viewer)
        self.assertIn("effectiveSurfaceVisible", viewer)
        self.assertIn("structure.visible && structure.surfaceVisible === true", viewer)
        self.assertNotIn("interaction.isolatedLabelId", viewer)

    def test_restore_control_and_cache_identity_are_explicit(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        self.assertIn('id="segmentationStructureRestoreIsolation"', html)
        self.assertIn('data-structure-action="restore-isolation"', html)
        self.assertIn("phase6f-b-r1", html)
        self.assertIn("phase6f-b-r1", app)
        self.assertIn("syncSegmentationOverlayPresentationStatus", app)
        self.assertIn("effectiveVisible", app)
        self.assertIn("grid-template-columns: repeat(4", css)

    def test_6fb_does_not_enable_later_interaction_features(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "web/index.html",
                ROOT / "web/js/segmentation-structure-panel.js",
                ROOT / "web/js/segmentation-structure-interaction.js",
            )
        )
        self.assertNotIn("segmentationStructureClipParticipation", combined)
        self.assertNotIn("segmentationStructureExplode", combined)
        self.assertNotIn("exploded view", combined.lower())


if __name__ == "__main__":
    unittest.main()
