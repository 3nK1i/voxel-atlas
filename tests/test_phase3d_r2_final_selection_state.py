from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase3DR2FinalSelectionStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        self.js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")

    def test_anatomical_layer_active_state_shares_directional_cut_effect(self) -> None:
        selector_group = (
            '.viewer-tool-button[aria-pressed="true"],\n'
            '.direction-button.is-active,\n'
            '.layer-button.is-active {'
        )
        self.assertIn(selector_group, self.css)
        self.assertIn("linear-gradient(", self.css)
        self.assertIn("inset 0 0 0 1px", self.css)
        self.assertIn("0 0 15px", self.css)

    def test_layer_buttons_expose_pressed_state(self) -> None:
        self.assertEqual(self.html.count('data-layer="'), 1)
        self.assertIn(
            'class="layer-button is-active" data-layer="volume" disabled aria-pressed="true"',
            self.html,
        )
        self.assertIn('volumeLayerButton.setAttribute("aria-pressed", "true")', self.js)

    def test_full_volume_is_disabled_until_verified_texture_is_ready(self) -> None:
        self.assertIn(".layer-button:disabled", self.css)
        self.assertIn("opacity: 0.40;", self.css)
        self.assertIn('data-layer="volume" disabled aria-pressed="true"', self.html)
        self.assertIn("volumeLayerButton.disabled = !volumeLayer.available", self.js)
        self.assertNotIn('data-layer="brain"', self.html)
        self.assertNotIn('data-layer="combined"', self.html)

    def test_layer_transition_includes_glow_properties(self) -> None:
        self.assertIn(
            "transition: border-color 130ms ease, background 130ms ease, color 130ms ease, box-shadow 130ms ease, transform 130ms ease;",
            self.css,
        )

    def test_final_cache_bust_is_present(self) -> None:
        self.assertIn('/css/styles.css?v=phase3d-r2', self.html)
        self.assertIn('/js/app.js?v=phase3d-r21-phase4h3b', self.html)


if __name__ == "__main__":
    unittest.main()
