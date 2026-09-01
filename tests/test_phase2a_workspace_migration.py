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


class Phase2AWorkspaceMigrationTests(unittest.TestCase):
    def test_workspace_remains_threejs_not_legacy_model_viewer(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        lowered = html.lower()
        self.assertIn('data-workspace="voxelatlas-v1"', html)
        self.assertIn("VoxelAtlas", html)
        self.assertIn("three@0.185.1", html)
        self.assertIn('id="viewport"', html)
        self.assertNotIn("model-viewer", lowered)
        self.assertNotIn("medical 3d skull demo", lowered)
        self.assertNotIn("view in ar", lowered)
        self.assertNotIn("premium xr", lowered)
        self.assertNotIn("holographic", lowered)
        self.assertNotIn("data-preset", lowered)

    def test_directional_cut_and_core_actions_remain_available(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for marker in (
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

    def test_specialized_retired_cut_behavior_is_absent(self) -> None:
        text = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in ("web/index.html", "web/js/app.js")
        ).lower()
        for marker in (
            "cran" + "ial",
            "aper" + "ture",
            "cut" + "away",
            "opening" + "slider",
            "opening" + "value",
            "opening" + "description",
            "skull_" + "open",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_layer_contract_is_structural_without_faking_patient_anatomy(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        model_readme = (ROOT / "web/assets/models/README.md").read_text(encoding="utf-8")

        self.assertIn('data-layer="volume"', html)
        self.assertIn('data-layer="skull"', html)
        self.assertIn('data-layer="brain"', html)
        self.assertIn('data-layer="combined"', html)
        self.assertIn('data-layer="volume" disabled', html)
        self.assertIn('data-layer="brain" disabled', html)
        self.assertIn('data-layer="combined" disabled', html)
        self.assertIn("layerRegistry", js)
        self.assertNotIn("/assets/models/brain.glb", js)
        self.assertIn("patient-specific", model_readme.lower())
        self.assertIn("browser must never fabricate", model_readme.lower())

    def test_directional_clipping_and_clinical_rendering_remain(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("renderer.localClippingEnabled", js)
        self.assertIn("sectionPlane", js)
        self.assertIn("MeshPhysicalMaterial", js)
        self.assertIn("0xe8e1d6", js)
        for forbidden in ("presetButtons", "presetConfig", "applyPreset", "AR_URL", "activateAR", "window.open("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, js)

    def test_prototypes_are_intentionally_retired_from_current_tree(self) -> None:
        self.assertFalse((ROOT / "prototypes/v2b3a").exists())
        self.assertFalse((ROOT / "prototypes/v2b3b").exists())
        self.assertFalse((ROOT / "scripts/check_v2b3a_prototype.py").exists())
        self.assertFalse((ROOT / "scripts/check_v2b3b_prototype.py").exists())

    def test_authenticated_workspace_route_serves_current_workspace(self) -> None:
        with TestClient(create_app(settings=make_settings())) as client:
            login = client.post(
                "/api/auth/login",
                json={"username": "engineer", "password": "correct horse battery staple"},
            )
            workspace = client.get("/workspace", follow_redirects=False)

        self.assertEqual(login.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertIn('data-workspace="voxelatlas-v1"', workspace.text)
        self.assertIn("Directional Cut", workspace.text)
        self.assertNotIn("View in AR", workspace.text)

    def test_workspace_logout_copy_is_concise(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="logoutButton"', html)
        self.assertIn(">Logout</button>", html)
        self.assertNotIn("Sign out", html)

    def test_login_heading_is_concise(self) -> None:
        html = (ROOT / "web/login.html").read_text(encoding="utf-8")
        self.assertIn('<h1 id="loginTitle">Login</h1>', html)
        self.assertNotIn("Welcome Back", html)

    def test_initial_camera_framing_preserves_accepted_distance(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        for marker in ("radius * 1.30", "radius * 0.42", "radius * 2.55", "radius * 1.15", "radius * 8"):
            with self.subTest(marker=marker):
                self.assertIn(marker, js)
        self.assertNotIn("radius * 0.84", js)
        self.assertNotIn("radius * 1.50", js)

    def test_production_app_uses_plain_hyphens_not_em_dashes(self) -> None:
        for relative in ("web/index.html", "web/login.html", "web/js/app.js", "web/js/login.js"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertNotIn("—", text)


if __name__ == "__main__":
    unittest.main()
