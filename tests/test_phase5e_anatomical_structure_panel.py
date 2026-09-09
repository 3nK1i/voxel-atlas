from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.segmentation_overlays import color_for_label  # noqa: E402
from voxelatlas.segmentation_structures import (  # noqa: E402
    TOTAL_SEGMENTATOR_TOTAL_STRUCTURES,
    build_structure_catalog,
)


class Phase5EStructureCatalogTests(unittest.TestCase):
    def test_totalsegmentator_total_taxonomy_is_complete_and_stable(self) -> None:
        self.assertEqual(len(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES), 117)
        self.assertEqual(
            sorted(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES),
            list(range(1, 118)),
        )
        self.assertEqual(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES[1], "spleen")
        self.assertEqual(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES[51], "heart")
        self.assertEqual(TOTAL_SEGMENTATOR_TOTAL_STRUCTURES[90], "brain")
        self.assertEqual(
            TOTAL_SEGMENTATOR_TOTAL_STRUCTURES[117],
            "costal_cartilages",
        )

    def test_catalog_exposes_only_present_labels_with_groups_and_palette(self) -> None:
        catalog = build_structure_catalog(
            provider_id="totalsegmentator",
            model_id="total",
            present_labels=[1, 51, 79, 90, 117],
            palette={
                label: color_for_label(label)
                for label in (1, 51, 79, 90, 117)
            },
        )

        self.assertEqual(catalog["schema_version"], 1)
        self.assertEqual(catalog["structure_count"], 5)
        self.assertEqual(
            [item["label_id"] for item in catalog["structures"]],
            [1, 51, 79, 90, 117],
        )
        by_label = {
            item["label_id"]: item
            for item in catalog["structures"]
        }
        self.assertEqual(by_label[1]["display_name"], "Spleen")
        self.assertEqual(by_label[51]["group_id"], "cardiovascular")
        self.assertEqual(by_label[79]["group_id"], "nervous_system")
        self.assertEqual(by_label[90]["display_name"], "Brain")
        self.assertEqual(by_label[117]["group_id"], "skeletal")
        self.assertEqual(
            by_label[117]["color_hex"],
            color_for_label(117),
        )
        self.assertEqual(by_label[117]["default_opacity"], 1.0)
        self.assertTrue(all(group["structure_count"] > 0 for group in catalog["groups"]))

        sided = build_structure_catalog(
            provider_id="totalsegmentator",
            model_id="total",
            present_labels=[2, 50, 92],
            palette={label: color_for_label(label) for label in (2, 50, 92)},
        )
        self.assertEqual(
            [item["display_name"] for item in sided["structures"]],
            ["Right Kidney", "Vertebra C1", "Left Rib 1"],
        )

    def test_unknown_provider_uses_explicit_provider_neutral_fallback(self) -> None:
        catalog = build_structure_catalog(
            provider_id="example-provider",
            model_id="example-model",
            present_labels=[7],
            palette={7: "#123456"},
        )
        structure = catalog["structures"][0]
        self.assertEqual(structure["name"], "label_7")
        self.assertEqual(structure["display_name"], "Label 7")
        self.assertEqual(structure["group_id"], "other")
        self.assertEqual(structure["color_hex"], "#123456")

    def test_catalog_rejects_background_duplicates_and_missing_colors(self) -> None:
        cases = (
            ([0, 1], {0: "#000000", 1: "#ffffff"}),
            ([1, 1], {1: "#ffffff"}),
            ([1], {}),
        )
        for labels, palette in cases:
            with self.subTest(labels=labels, palette=palette):
                with self.assertRaises(ValueError):
                    build_structure_catalog(
                        provider_id="totalsegmentator",
                        model_id="total",
                        present_labels=labels,
                        palette=palette,
                    )

    def test_phase5d_descriptor_adds_the_phase5e_catalog_without_changing_palette(self) -> None:
        from tests.test_phase5d_synchronized_mpr_segmentation_overlay import (
            make_service,
            write_volume,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_volume(root)
            descriptor = make_service(root).descriptor_latest()

        self.assertEqual(descriptor["present_labels"], [1, 7])
        self.assertEqual(
            descriptor["structure_catalog"]["structure_count"],
            2,
        )
        self.assertEqual(
            [item["label_id"] for item in descriptor["structure_catalog"]["structures"]],
            [1, 7],
        )


class Phase5EFrontendContractTests(unittest.TestCase):
    def test_structure_panel_is_progressive_and_has_all_required_controls(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "web" / "css" / "styles.css").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        module = (
            ROOT / "web" / "js" / "segmentation-structure-panel.js"
        ).read_text(encoding="utf-8")

        required_ids = (
            "segmentationStructurePanel",
            "segmentationStructureSearch",
            "segmentationStructureGroups",
            "segmentationStructureShowAll",
            "segmentationStructureHideAll",
            "segmentationStructureReset",
            "segmentationStructureColor",
            "segmentationStructureOpacity",
        )
        for control_id in required_ids:
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("structure-group", css)
        self.assertIn("SegmentationStructurePanel", module)
        self.assertIn("isolate", module.lower())
        self.assertIn("redrawSegmentationOverlays", app)
        self.assertNotIn("clinical-grade", (html + app + module).lower())

    def test_phase5e_browser_contract_probe_exists(self) -> None:
        probe = ROOT / "scripts" / "check_phase5e_structure_panel.mjs"
        self.assertTrue(probe.is_file())


if __name__ == "__main__":
    unittest.main()
