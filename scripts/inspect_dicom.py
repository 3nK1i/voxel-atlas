from pathlib import Path
import SimpleITK as sitk
import numpy as np

dicom_dir = Path("data/dicom")

if not dicom_dir.exists():
    raise SystemExit(f"Missing directory: {dicom_dir}")

reader = sitk.ImageSeriesReader()
series_ids = reader.GetGDCMSeriesIDs(str(dicom_dir))

print("===== DICOM SERIES DISCOVERY =====")
if not series_ids:
    raise SystemExit("No DICOM series found.")

print(f"Series count: {len(series_ids)}")
for i, sid in enumerate(series_ids, 1):
    files = reader.GetGDCMSeriesFileNames(str(dicom_dir), sid)
    print(f"  [{i}] SeriesInstanceUID: {sid}")
    print(f"      file count: {len(files)}")

# Use the first / only discovered series
series_id = series_ids[0]
files = reader.GetGDCMSeriesFileNames(str(dicom_dir), series_id)
reader.SetFileNames(files)

image = reader.Execute()
array = sitk.GetArrayFromImage(image)  # z, y, x

size = image.GetSize()
spacing = image.GetSpacing()
origin = image.GetOrigin()
direction = image.GetDirection()

print()
print("===== VOLUME METADATA =====")
print(f"Series UID       : {series_id}")
print(f"Volume size      : {size}  (x, y, z)")
print(f"Array shape      : {array.shape}  (z, y, x)")
print(f"Spacing (mm)     : {spacing}")
print(f"Origin           : {origin}")
print(f"Direction        : {direction}")

print()
print("===== INTENSITY / HU CHECK =====")
print(f"dtype            : {array.dtype}")
print(f"min              : {array.min()}")
print(f"max              : {array.max()}")
print(f"mean             : {array.mean():.2f}")
print(f"std              : {array.std():.2f}")

# Physical extent
extent_mm = tuple((size[i] - 1) * spacing[i] for i in range(3))
print()
print("===== PHYSICAL EXTENT =====")
print(f"Extent (mm)      : {extent_mm}")

# Slice-to-slice z consistency using image position patient
print()
print("===== SLICE POSITION CHECK =====")
z_positions = []
for f in files:
    img = sitk.ReadImage(f)
    z_positions.append(img.GetOrigin()[2])

z_positions = np.array(sorted(z_positions), dtype=np.float64)
if len(z_positions) > 1:
    z_diffs = np.diff(z_positions)
    print(f"Slice count      : {len(z_positions)}")
    print(f"z min/max        : {z_positions[0]:.3f} / {z_positions[-1]:.3f}")
    print(f"z diff min/max   : {z_diffs.min():.6f} / {z_diffs.max():.6f}")
    print(f"z diff mean      : {z_diffs.mean():.6f}")
else:
    print("Only one slice found.")

# Quick sanity on middle slices
z_mid = array.shape[0] // 2
y_mid = array.shape[1] // 2
x_mid = array.shape[2] // 2

print()
print("===== MID-SLICE SHAPES =====")
print(f"Axial slice      : {array[z_mid].shape}")
print(f"Coronal slice    : {array[:, y_mid, :].shape}")
print(f"Sagittal slice   : {array[:, :, x_mid].shape}")

print()
print("INSPECTION_OK")
