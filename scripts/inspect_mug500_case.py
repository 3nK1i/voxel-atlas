from pathlib import Path

import numpy as np
import SimpleITK as sitk


PATH = Path("data/mug500/A0101/A0101.nrrd")

image = sitk.ReadImage(str(PATH))
array = sitk.GetArrayFromImage(image)

print("===== MUG500+ A0101 =====")
print("File             :", PATH)
print("Size             :", image.GetSize())
print("Array shape      :", array.shape, "(z,y,x)")
print("Spacing (mm)     :", image.GetSpacing())
print("Origin           :", image.GetOrigin())
print("Direction        :", image.GetDirection())
print("Pixel type       :", image.GetPixelIDTypeAsString())
print("dtype            :", array.dtype)
print("min/max          :", array.min(), "/", array.max())

values, counts = np.unique(array, return_counts=True)

print()
print("===== VALUES =====")

if len(values) <= 20:
    for value, count in zip(values, counts):
        print(f"{value!r:12} : {int(count):,} voxels")
else:
    print("Unique values    :", len(values))
    print("First values     :", values[:10])
    print("Last values      :", values[-10:])

foreground = array != 0

print()
print("===== FOREGROUND =====")
print("Foreground voxels:", f"{int(foreground.sum()):,}")
print("Foreground       :", f"{foreground.mean() * 100:.3f}%")

coords = np.argwhere(foreground)

if len(coords):
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)

    print("Voxel bbox zyx   :", tuple(lo), "->", tuple(hi))
else:
    print("WARNING: no foreground voxels")

print()
print("MUG500_INSPECTION_OK")
