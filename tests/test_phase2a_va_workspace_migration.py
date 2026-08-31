from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from voxelatlas import config  # noqa: E402
from voxelatlas.app import create_app  # noqa: E402
from voxelatlas.passwords import hash_password  # noqa: E402


def make_settings() -> config.AppSettings:
    return config.AppSettings(
        environment="test",
        session_secret="x" * 48,
        secure_cookies=False,
        session_cookie_name="voxelatlas_session",
        allowed_hosts=("testserver", "127.0.0.1", "localhost"),
        data_dir=ROOT / "data",
        max_upload_mib=512,
        auth_username="engineer",
        auth_password_hash=hash_password("correct horse battery staple"),
        session_ttl_minutes=60,
    )


class Phase2AVAWorkspaceMigrationTests(unittest.TestCase):
    def test_workspace_is_voxelatlas_threejs_va_shell_not_legacy_model_viewer(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        lowered = html.lower()
        self.assertIn('data-workspace="voxelatlas-va"', html)
        self.assertIn("VoxelAtlas", html)
        self.assertIn("three@0.185.1", html)
        self.assertIn('id="viewport"', html)
        self.assertNotIn("model-viewer", lowered)
        self.assertNotIn("medical 3d skull demo", lowered)
        self.assertNotIn("view in ar", lowered)
        self.assertNotIn("premium xr", lowered)
        self.assertNotIn("holographic", lowered)
        self.assertNotIn("data-preset", lowered)

    def test_workspace_exposes_required_va_controls(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for marker in (
            'id="openingSlider"',
            'id="sectionSlider"',
            'data-section-axis="y"',
            'data-section-axis="z"',
            'data-section-axis="x"',
            'id="opacitySlider"',
            'id="resetButton"',
            'id="autoRotateButton"',
            'id="logoutButton"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

    def test_anatomical_layer_contract_is_explicit_without_faking_brain(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        model_readme = (ROOT / "web/assets/models/README.md").read_text(encoding="utf-8")

        self.assertIn('data-layer="skull"', html)
        self.assertIn('data-layer="brain"', html)
        self.assertIn('data-layer="combined"', html)
        self.assertIn('data-layer="brain" disabled', html)
        self.assertIn('data-layer="combined" disabled', html)
        self.assertIn("/assets/models/brain.glb", js)
        self.assertIn("brain.glb", model_readme)
        self.assertIn("not generated or substituted", model_readme.lower())

    def test_workspace_js_preserves_va_dynamic_cranial_aperture(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        for marker in (
            "uApertureCenter",
            "uApertureMaxRadii",
            "uMinSuperiorRadius",
            "sqrt(",
            "centerAboveFraction",
            "maxRadiusXFraction",
            "targetOpening",
            "currentOpening",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)
        self.assertIn("0.58", js)

    def test_workspace_js_uses_directional_clipping_and_clinical_only_rendering(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("renderer.localClippingEnabled", js)
        self.assertIn("sectionPlane", js)
        self.assertIn("MeshPhysicalMaterial", js)
        self.assertIn("0xeff5fa", js)
        for forbidden in (
            "presetButtons",
            "presetConfig",
            "applyPreset",
            "AR_URL",
            "activateAR",
            "window.open(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, js)

    def test_vb_is_retired_while_va_reference_remains_byte_preserved(self) -> None:
        self.assertTrue((ROOT / "prototypes/v2b3a/index.html").is_file())
        self.assertTrue((ROOT / "prototypes/v2b3a/app.js").is_file())
        self.assertTrue((ROOT / "prototypes/v2b3a/assets/skull_full.glb").is_file())
        self.assertFalse((ROOT / "prototypes/v2b3b").exists())
        self.assertFalse((ROOT / "scripts/check_v2b3b_prototype.py").exists())

    def test_baseline_contract_records_intentional_vb_retirement(self) -> None:
        checker = (ROOT / "scripts/check_phase0c1_baseline_integrity.py").read_text(encoding="utf-8")
        runner = (ROOT / "scripts/run_phase0c1_checks.sh").read_text(encoding="utf-8")
        handoff = (ROOT / "docs/baseline/VERIFIED_HANDOFF.md").read_text(encoding="utf-8")
        phase0 = (ROOT / "docs/phase_history/PHASE0C1_BASELINE_PRESERVATION.md").read_text(encoding="utf-8")
        self.assertIn("prototypes/v2b3a", checker)
        self.assertNotIn("prototypes/v2b3b", checker)
        self.assertNotIn("check_v2b3b_prototype.py", runner)
        self.assertIn("retired", handoff.lower())
        self.assertIn("phase 2a", handoff.lower())
        self.assertIn("retired", phase0.lower())

    def test_authenticated_workspace_route_serves_migrated_va_workspace(self) -> None:
        with TestClient(create_app(settings=make_settings())) as client:
            login = client.post(
                "/api/auth/login",
                json={
                    "username": "engineer",
                    "password": "correct horse battery staple",
                },
            )
            workspace = client.get("/workspace", follow_redirects=False)

        self.assertEqual(login.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertIn('data-workspace="voxelatlas-va"', workspace.text)
        self.assertIn("Cranial opening", workspace.text)
        self.assertNotIn("View in AR", workspace.text)

    def test_workspace_logout_copy_is_concise(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="logoutButton"', html)
        self.assertIn(">\n          Logout\n        </button>", html)
        self.assertNotIn("Sign out", html)

    def test_login_heading_is_concise(self) -> None:
        html = (ROOT / "web/login.html").read_text(encoding="utf-8")
        self.assertIn('<h1 id="loginTitle">Login</h1>', html)
        self.assertNotIn("Welcome Back", html)

    def test_initial_camera_framing_preserves_va_reference_distance(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        for marker in (
            "radius * 1.30",
            "radius * 0.42",
            "radius * 2.55",
            "radius * 1.15",
            "radius * 8",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)
        self.assertNotIn("radius * 0.84", js)
        self.assertNotIn("radius * 1.50", js)

    def test_production_app_uses_plain_hyphens_not_em_dashes(self) -> None:
        index_html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        login_html = (ROOT / "web/login.html").read_text(encoding="utf-8")
        self.assertIn("<title>VoxelAtlas - Anatomy Workspace</title>", index_html)
        self.assertIn("<title>VoxelAtlas - Login</title>", login_html)
        self.assertNotIn("—", index_html)
        self.assertNotIn("—", login_html)

    def test_v1_roadmap_prioritizes_layers_and_moves_atlas_post_v1(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Skull", readme)
        self.assertIn("Brain", readme)
        self.assertIn("Skull + Brain", readme)
        self.assertIn("Atlas", readme)
        self.assertIn("post-V1", readme)


if __name__ == "__main__":
    unittest.main()
