from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from voxelatlas.segmentation_label_maps import SegmentationLabelMapService
from voxelatlas.segmentation_surfaces import _safe_surface_temp_root


class Post6FProductionRuntimePermissionTests(unittest.TestCase):
    def test_label_map_repository_does_not_chmod_shared_segmentation_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="voxelatlas-permissions-") as tmp:
            data_dir = Path(tmp)
            segmentation_root = data_dir / "segmentation"
            maps_root = segmentation_root / "label-maps"

            segmentation_root.mkdir(mode=0o755)
            maps_root.mkdir(mode=0o700)

            real_chmod = os.chmod

            def guarded_chmod(path: os.PathLike[str] | str, mode: int) -> None:
                candidate = Path(path)
                if candidate == segmentation_root:
                    raise PermissionError(
                        1,
                        "Operation not permitted",
                        str(segmentation_root),
                    )
                real_chmod(path, mode)

            service = SegmentationLabelMapService(data_dir=data_dir)

            with mock.patch(
                "voxelatlas.segmentation_label_maps.os.chmod",
                side_effect=guarded_chmod,
            ) as chmod_mock:
                service._ensure_root()

            self.assertTrue(maps_root.is_dir())
            self.assertFalse(
                any(
                    Path(call.args[0]) == segmentation_root
                    for call in chmod_mock.call_args_list
                )
            )

    def test_surface_temp_repository_does_not_chmod_shared_segmentation_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="voxelatlas-permissions-") as tmp:
            data_dir = Path(tmp)
            segmentation_root = data_dir / "segmentation"
            surface_tmp = segmentation_root / "surface-tmp"

            segmentation_root.mkdir(mode=0o755)
            surface_tmp.mkdir(mode=0o700)

            real_chmod = os.chmod

            def guarded_chmod(path: os.PathLike[str] | str, mode: int) -> None:
                candidate = Path(path)
                if candidate == segmentation_root:
                    raise PermissionError(
                        1,
                        "Operation not permitted",
                        str(segmentation_root),
                    )
                real_chmod(path, mode)

            with mock.patch(
                "voxelatlas.segmentation_surfaces.os.chmod",
                side_effect=guarded_chmod,
            ) as chmod_mock:
                result = _safe_surface_temp_root(data_dir)

            self.assertEqual(result, surface_tmp)
            self.assertTrue(surface_tmp.is_dir())
            self.assertFalse(
                any(
                    Path(call.args[0]) == segmentation_root
                    for call in chmod_mock.call_args_list
                )
            )


if __name__ == "__main__":
    unittest.main()
