from pathlib import Path

import numpy as np
import SimpleITK as sitk


PATH = Path("data/mug500/A0101/A0101.nrrd")

image = sitk.ReadImage(str(PATH))
mask = sitk.Cast(image > 0, sitk.sitkUInt8)

size = image.GetSize()

cc = sitk.ConnectedComponent(mask)

stats = sitk.LabelShapeStatisticsImageFilter()
stats.Execute(cc)

components = []

for label in stats.GetLabels():
    bbox = stats.GetBoundingBox(label)
    x, y, z, sx, sy, sz = bbox

    touches = {
        "x0": x == 0,
        "x1": x + sx >= size[0],
        "y0": y == 0,
        "y1": y + sy >= size[1],
        "z0": z == 0,
        "z1": z + sz >= size[2],
    }

    components.append(
        {
            "label": label,
            "voxels": stats.GetNumberOfPixels(label),
            "volume_mm3": stats.GetPhysicalSize(label),
            "centroid": stats.GetCentroid(label),
            "bbox": bbox,
            "touches": touches,
        }
    )

components.sort(
    key=lambda item: item["voxels"],
    reverse=True,
)

print("===== MUG500 COMPONENT ANALYSIS =====")
print("Volume size :", size)
print("Components  :", len(components))
print()

for rank, item in enumerate(components[:30], start=1):
    touched = [
        key for key, value in item["touches"].items()
        if value
    ]

    print(f"Component #{rank}")
    print(f"  label       : {item['label']}")
    print(f"  voxels      : {item['voxels']:,}")
    print(f"  volume mm3  : {item['volume_mm3']:,.1f}")
    print(
        "  centroid mm :",
        tuple(round(v, 2) for v in item["centroid"]),
    )
    print(f"  bbox        : {item['bbox']}")
    print(
        "  boundaries  :",
        ", ".join(touched) if touched else "none",
    )
    print()

print("MUG500_COMPONENTS_OK")
