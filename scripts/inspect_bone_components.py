from pathlib import Path

import SimpleITK as sitk


DICOM_DIR = Path("data/dicom")
THRESHOLD = 300


reader = sitk.ImageSeriesReader()
series_ids = reader.GetGDCMSeriesIDs(str(DICOM_DIR))

if not series_ids:
    raise RuntimeError("No DICOM series found.")

files = reader.GetGDCMSeriesFileNames(
    str(DICOM_DIR),
    series_ids[0],
)

reader.SetFileNames(files)
image = reader.Execute()


mask = sitk.BinaryThreshold(
    image,
    lowerThreshold=THRESHOLD,
    upperThreshold=32767,
    insideValue=1,
    outsideValue=0,
)

cc = sitk.ConnectedComponent(mask)

stats = sitk.LabelShapeStatisticsImageFilter()
stats.Execute(cc)

components = []

for label in stats.GetLabels():
    components.append(
        (
            label,
            stats.GetNumberOfPixels(label),
            stats.GetPhysicalSize(label),
            stats.GetCentroid(label),
            stats.GetBoundingBox(label),
        )
    )

components.sort(key=lambda x: x[1], reverse=True)

print("===== BONE COMPONENT ANALYSIS =====")
print(f"Threshold: {THRESHOLD} HU")
print(f"Components: {len(components)}")
print()

for rank, (label, voxels, volume_mm3, centroid, bbox) in enumerate(
    components[:20],
    start=1,
):
    print(f"Component #{rank}")
    print(f"  label       : {label}")
    print(f"  voxels      : {voxels:,}")
    print(f"  volume mm3  : {volume_mm3:,.1f}")
    print(f"  centroid mm : {tuple(round(v, 2) for v in centroid)}")
    print(f"  bbox voxels : {bbox}")
    print()

print("COMPONENT_INSPECTION_OK")
