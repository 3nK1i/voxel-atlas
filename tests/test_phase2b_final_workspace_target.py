from __future__ import annotations

import hashlib
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

TARGET_SHA256 = "02994e3e1bd56e914d4da1c442c1037346699f67ddeffd6c47d962656af92c9d"


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Phase2BFinalWorkspaceTargetTests(unittest.TestCase):
    def test_authoritative_v1_workspace_target_is_frozen(self) -> None:
        target = ROOT / "design/reference/workspace_v1_target.png"
        self.assertTrue(target.is_file())
        self.assertEqual(sha256(target), TARGET_SHA256)

        sums = (ROOT / "design/reference/SHA256SUMS").read_text(encoding="utf-8")
        visual_contract = (ROOT / "docs/design/VISUAL_REFERENCE_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn(f"{TARGET_SHA256}  workspace_v1_target.png", sums)
        self.assertIn("workspace_v1_target.png", visual_contract)
        self.assertIn("95-100%", visual_contract)
        self.assertIn("must never be used as a page background", visual_contract.lower())

    def test_workspace_matches_locked_v1_shell_structure(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for marker in (
            'data-workspace="voxelatlas-v1"',
            'id="themeToggle"',
            'id="workflowData"',
            'id="workflowReconstruction"',
            'id="workflowVisualization"',
            'id="uploadDicomButton"',
            'id="studyPanel"',
            'id="reconstructionPanel"',
            'id="viewport"',
            'id="mprAxial"',
            'id="mprCoronal"',
            'id="mprSagittal"',
            'id="directionalCutPanel"',
            'id="anatomicalLayersPanel"',
            'id="opacitySlider"',
            'id="resetButton"',
            'id="autoRotateButton"',
            'id="logoutButton"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

    def test_directional_cut_is_the_only_sectioning_system(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        for marker in (
            'data-section-axis="y"',
            'data-section-axis="z"',
            'data-section-axis="x"',
            'id="sectionSlider"',
            "renderer.localClippingEnabled",
            "sectionPlane",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html + js)

        forbidden = (
            "cran" + "ial",
            "aper" + "ture",
            "cut" + "away",
            "opening" + "Slider",
            "opening" + "Value",
            "opening" + "Description",
            "skull_" + "open",
        )
        combined = (html + "\n" + js).lower()
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker.lower(), combined)

    def test_retired_specialized_prototype_and_assets_are_absent(self) -> None:
        retired = (
            "prototypes/v2b3a",
            "prototypes/v2b3b",
            "scripts/check_v2b3a_prototype.py",
            "scripts/check_v2b3b_prototype.py",
            "scripts/rebuild_a0101_open_canonical.py",
            "scripts/build_a0101_oval_" + "cut" + "away_candidates.py",
            "scripts/build_a0101_" + "cut" + "away_candidates.py",
            "scripts/view_a0101_oval_" + "cut" + "away_candidates.py",
            "scripts/view_a0101_" + "cut" + "away_candidates.py",
            "scripts/build_a0101_premium_web_assets.py",
            "web/assets/models/skull_" + "open.glb",
        )
        for relative in retired:
            with self.subTest(relative=relative):
                self.assertFalse((ROOT / relative).exists())

    def test_theme_toggle_has_real_dark_and_light_implementations(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        self.assertIn('aria-label="Switch to light mode"', html)
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("voxelatlas-theme", js)
        self.assertIn("matchMedia", js)
        self.assertIn("themeToggle", js)

    def test_workspace_does_not_fake_mpr_data_before_volume_reconstruction(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        self.assertIn('id="uploadDicomButton"', html)
        self.assertEqual(html.count('data-volume-state="empty"'), 3)
        self.assertIn("DICOM volume not loaded", html)
        self.assertNotIn("slice-placeholder.jpg", html)

    def test_anatomical_layer_architecture_is_truthful_and_extensible(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")

        for marker in (
            'data-layer="volume"',
            'data-layer="skull"',
            'data-layer="brain"',
            'data-layer="combined"',
            'data-future-layer="skin"',
            'data-future-layer="sinuses"',
            'data-future-layer="vessels"',
            "layerRegistry",
            "registerLayer",
            "setLayerAvailability",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html + js)

        self.assertIn('data-layer="volume" disabled', html)
        self.assertIn('data-layer="brain" disabled', html)
        self.assertIn('data-layer="combined" disabled', html)
        self.assertNotIn("/assets/models/brain.glb", js)

    def test_viewer_toolbar_controls_have_real_handlers(self) -> None:
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        for marker in (
            'id="fitViewButton"',
            'id="zoomInButton"',
            'id="zoomOutButton"',
            'id="fullscreenButton"',
            "fitViewButton.addEventListener",
            "zoomInButton.addEventListener",
            "zoomOutButton.addEventListener",
            "fullscreenButton.addEventListener",
            "requestFullscreen",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, html + js)

    def test_authenticated_route_serves_final_v1_workspace_shell(self) -> None:
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
        self.assertIn("Axial", workspace.text)
        self.assertIn("Coronal", workspace.text)
        self.assertIn("Sagittal", workspace.text)

    def test_production_ui_excludes_non_v1_modes_and_em_dashes(self) -> None:
        files = (
            ROOT / "web/index.html",
            ROOT / "web/login.html",
            ROOT / "web/js/app.js",
            ROOT / "web/js/login.js",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in files)
        lowered = text.lower()
        for forbidden in ("view in ar", "premium xr", "holographic", "data-preset", "—"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered if forbidden != "—" else text)

    def test_workspace_visual_scale_matches_locked_target_density(self) -> None:
        css = (ROOT / "web/css/styles.css").read_text(encoding="utf-8")
        self.assertIn("--header-height: 72px;", css)
        self.assertIn("--left-width: clamp(250px, 17vw, 330px);", css)
        self.assertIn("--right-width: clamp(285px, 19vw, 360px);", css)
        self.assertIn("width: calc(100% - 16px);", css)
        self.assertNotIn("width: min(1600px, calc(100% - 12px));", css)
        self.assertIn("grid-template-rows: minmax(320px, 1fr) minmax(220px, 34%);", css)

    def test_clinical_material_avoids_near_opaque_triangle_sorting_artifacts(self) -> None:
        js = (ROOT / "web/js/app.js").read_text(encoding="utf-8")
        self.assertIn("renderer.toneMappingExposure = 0.86;", js)
        self.assertIn("depthWrite: true", js)
        self.assertIn("side: THREE.FrontSide", js)
        self.assertNotIn("mesh.material.depthWrite = state.opacity >= 0.995", js)

    def test_phase2b_runner_is_compact_on_success_and_verbose_on_failure(self) -> None:
        runner = (ROOT / "scripts/run_phase2b_checks.sh").read_text(encoding="utf-8")
        self.assertIn("run_quiet", runner)
        self.assertIn('cat "$log"', runner)
        self.assertIn("PASS", runner)
        self.assertIn("FAIL", runner)


if __name__ == "__main__":
    unittest.main()
