from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase6BRefinedSurfaceAccurateFallbackContracts(unittest.TestCase):
    def test_viewer_declares_narrow_refined_to_accurate_fallback(self) -> None:
        source = (ROOT / "web" / "js" / "segmentation-surface-viewer.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('requestedQuality === "refined"', source)
        self.assertIn('fallbackQuality === "accurate"', source)
        self.assertIn("response.status === 422", source)
        self.assertIn("presentationFallback", source)
        self.assertIn("accurate fallback", source)

    def test_cache_busts_surface_viewer_after_fallback_change(self) -> None:
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            "segmentation-surface-viewer.js?v=phase6a-r1-phase6b-r1-phase6c-r2-"
            "phase6d2b-r1-phase6e-b-r1-phase6e-d-r1-phase6f-b-r1-phase6b-fallback-r1",
            app,
        )
        self.assertIn("phase6f-b-r1-phase6b-fallback-r1", index)

    def test_fallback_does_not_modify_refinement_worker_policy(self) -> None:
        worker = (ROOT / "scripts" / "phase6b_surface_worker.py").read_text(encoding="utf-8")
        self.assertIn(
            "accurate reference topology cannot be repaired within bounded local face-only policy",
            worker,
        )
        service = (ROOT / "backend" / "voxelatlas" / "segmentation_surfaces.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES = 12", service)
        self.assertIn("REFINED_LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES = 6", service)


if __name__ == "__main__":
    unittest.main()
