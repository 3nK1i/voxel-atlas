from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import SimpleITK as sitk


DICOM_DIR = Path("data/dicom")
OUTPUT_DIR = Path("outputs/ct_inspection")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_series() -> sitk.Image:
    reader = sitk.ImageSeriesReader()
    ids = reader.GetGDCMSeriesIDs(str(DICOM_DIR))

    if not ids:
        raise RuntimeError("No DICOM series found.")

    if len(ids) != 1:
        raise RuntimeError(f"Expected one series, found {len(ids)}")

    files = reader.GetGDCMSeriesFileNames(str(DICOM_DIR), ids[0])
    reader.SetFileNames(files)
    return reader.Execute()


def window_ct(img: np.ndarray, center=500.0, width=2000.0):
    lo = center - width / 2.0
    hi = center + width / 2.0

    out = np.clip(img, lo, hi)
    return (out - lo) / (hi - lo)


image = load_series()

print("===== ORIGINAL GEOMETRY =====")
print("Size      :", image.GetSize())
print("Spacing   :", image.GetSpacing())
print("Origin    :", image.GetOrigin())
print("Direction :", image.GetDirection())

# Reorient losslessly to standard DICOM LPS axis order when the
# direction cosines correspond to an orthogonal anatomical acquisition.
canonical = sitk.DICOMOrient(image, "LPS")

print()
print("===== CANONICAL LPS GEOMETRY =====")
print("Size      :", canonical.GetSize())
print("Spacing   :", canonical.GetSpacing())
print("Origin    :", canonical.GetOrigin())
print("Direction :", canonical.GetDirection())

volume = sitk.GetArrayFromImage(canonical)  # z, y, x

print()
print("Array     :", volume.shape, "(z,y,x)")
print("HU range  :", int(volume.min()), "to", int(volume.max()))


# AXIAL: z fixed
z_indices = np.linspace(
    0,
    volume.shape[0] - 1,
    9,
    dtype=int,
)

fig, axes = plt.subplots(3, 3, figsize=(14, 14))

for ax, z in zip(axes.flat, z_indices):
    ax.imshow(
        window_ct(volume[z]),
        cmap="gray",
        origin="lower",
    )
    ax.set_title(f"Axial z={z}")
    ax.axis("off")

fig.tight_layout()
axial_path = OUTPUT_DIR / "axial_bone_montage.png"
fig.savefig(axial_path, dpi=160)
plt.close(fig)


# CORONAL: y fixed
y = volume.shape[1] // 2

fig, ax = plt.subplots(figsize=(9, 9))
ax.imshow(
    window_ct(volume[:, y, :]),
    cmap="gray",
    origin="lower",
    aspect="equal",
)
ax.set_title("Middle coronal — bone window")
ax.axis("off")

fig.tight_layout()
coronal_path = OUTPUT_DIR / "coronal_bone.png"
fig.savefig(coronal_path, dpi=160)
plt.close(fig)


# SAGITTAL: x fixed
x = volume.shape[2] // 2

fig, ax = plt.subplots(figsize=(9, 9))
ax.imshow(
    window_ct(volume[:, :, x]),
    cmap="gray",
    origin="lower",
    aspect="equal",
)
ax.set_title("Middle sagittal — bone window")
ax.axis("off")

fig.tight_layout()
sagittal_path = OUTPUT_DIR / "sagittal_bone.png"
fig.savefig(sagittal_path, dpi=160)
plt.close(fig)


print()
print("===== OUTPUT =====")
print(axial_path)
print(coronal_path)
print(sagittal_path)
print()
print("CT_INSPECTION_OK")
