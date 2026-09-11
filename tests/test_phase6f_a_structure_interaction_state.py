from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase6FAStructureInteractionStateTests(unittest.TestCase):
    def test_interaction_module_defines_non_destructive_display_state(self) -> None:
        module_path = ROOT / "web" / "js" / "segmentation-structure-interaction.js"
        self.assertTrue(module_path.is_file())
        module = module_path.read_text(encoding="utf-8")

        required = (
            "STRUCTURE_INTERACTION_SCHEMA_VERSION",
            "createStructureInteractionState",
            "createStructureInteractionDefaults",
            "resolveStructureInteraction",
            "isolatedLabelId",
            "clippingEnabled",
            "explodedOffsetLpsMm",
            "effectiveVisible",
            "effectiveSurfaceVisible",
        )
        for token in required:
            self.assertIn(token, module)

        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "marching_cubes",
            "geometry.dispose",
            "new THREE",
            "vertices",
            "indices",
        ):
            self.assertNotIn(forbidden, module)

    def test_existing_structure_presentation_owns_new_interaction_state(self) -> None:
        panel = (ROOT / "web" / "js" / "segmentation-structure-panel.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("createStructureInteractionState", panel)
        self.assertIn("createStructureInteractionDefaults", panel)
        self.assertIn("resetStructureInteractionState", panel)
        self.assertIn("interaction: createStructureInteractionState()", panel)
        self.assertIn("clippingEnabled", panel)
        self.assertIn("explodedOffsetLpsMm", panel)

    def test_phase6f_a_does_not_activate_advanced_interaction_ui(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        panel = (ROOT / "web" / "js" / "segmentation-structure-panel.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("segmentationStructureRestoreIsolation", html)
        self.assertNotIn("segmentationStructureClipParticipation", html)
        self.assertNotIn("segmentationStructureExplode", html)
        # Phase 5E's current Iso control remains until 6F-B wires the new state model.
        self.assertIn('button("Iso", "structure-isolate", "isolate"', panel)

    def test_cache_keys_load_the_phase6f_a_foundation(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("phase6f-a-r1", html)
        self.assertIn("segmentation-structure-panel.js?v=", app)
        self.assertIn("phase6f-a-r1", app)

    def test_phase6f_a_roadmap_boundary_is_explicit(self) -> None:
        doc = (
            ROOT
            / "docs"
            / "phase_history"
            / "PHASE6F_A_STRUCTURE_INTERACTION_STATE_ARCHITECTURE.md"
        )
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        required = (
            "6F-A",
            "non-destructive",
            "Patient LPS",
            "6F-B",
            "6F-C",
            "6F-D",
            "6F-E",
            "6F-F",
            "No geometry rebuild",
            "No geometry fetch",
            "No clinical validation",
        )
        for token in required:
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
