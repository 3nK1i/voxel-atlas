from pathlib import Path

import json
import numpy as np
import pyvista as pv
import trimesh


SOURCE = Path(
    "data/mug500/A0101/A0101_clear.stl"
)

OUT_DIR = Path(
    "outputs/demo/A0101"
)

TARGET_TRIANGLES = 200_000

OUT_DIR.mkdir(parents=True, exist_ok=True)


print("===== A0101 DEMO ASSET =====")
print("Source:", SOURCE)

mesh = pv.read(SOURCE)
mesh = mesh.triangulate().clean()

print()
print("===== CLEAN REFERENCE =====")
print("Vertices  :", f"{mesh.n_points:,}")
print("Triangles :", f"{mesh.n_cells:,}")

bounds = mesh.bounds

extent_mm = np.array([
    bounds.x_max - bounds.x_min,
    bounds.y_max - bounds.y_min,
    bounds.z_max - bounds.z_min,
])

center_mm = np.array([
    (bounds.x_min + bounds.x_max) / 2.0,
    (bounds.y_min + bounds.y_max) / 2.0,
    (bounds.z_min + bounds.z_max) / 2.0,
])

print("Extent mm :", np.round(extent_mm, 3))
print("Center mm :", np.round(center_mm, 3))


# Preserve the full cleaned reference in original millimetre coordinates.
full_path = OUT_DIR / "A0101_demo_full_mm.ply"
mesh.save(full_path)


# Mobile optimization.
mobile = mesh

if mobile.n_cells > TARGET_TRIANGLES:
    reduction = 1.0 - (
        float(TARGET_TRIANGLES)
        / float(mobile.n_cells)
    )

    mobile = mobile.decimate(
        target_reduction=reduction,
        volume_preservation=True,
    ).clean()


print()
print("===== MOBILE =====")
print("Vertices  :", f"{mobile.n_points:,}")
print("Triangles :", f"{mobile.n_cells:,}")

mobile_bounds = mobile.bounds

mobile_extent_mm = np.array([
    mobile_bounds.x_max - mobile_bounds.x_min,
    mobile_bounds.y_max - mobile_bounds.y_min,
    mobile_bounds.z_max - mobile_bounds.z_min,
])

print("Extent mm :", np.round(mobile_extent_mm, 3))


mobile_ply = OUT_DIR / "A0101_demo_mobile_mm.ply"
mobile.save(mobile_ply)


# Convert to trimesh.
faces = mobile.faces.reshape(-1, 4)

if not np.all(faces[:, 0] == 3):
    raise RuntimeError("Expected triangular mesh.")


vertices_mm = np.asarray(
    mobile.points,
    dtype=np.float64,
)

triangles = np.asarray(
    faces[:, 1:4],
    dtype=np.int64,
)


# Center model for convenient AR rotation/placement,
# while preserving the original metric scale.
mobile_center_mm = vertices_mm.mean(axis=0)

vertices_m = (
    vertices_mm - mobile_center_mm
) / 1000.0


tm = trimesh.Trimesh(
    vertices=vertices_m,
    faces=triangles,
    process=False,
)

tm.remove_unreferenced_vertices()

tm.visual.vertex_colors = np.tile(
    np.array(
        [235, 232, 220, 255],
        dtype=np.uint8,
    ),
    (len(tm.vertices), 1),
)


glb_path = OUT_DIR / "A0101_demo_mobile_m.glb"

glb_path.write_bytes(
    tm.export(file_type="glb")
)


metadata = {
    "source": str(SOURCE),
    "source_units": "millimetres",
    "glb_units": "metres",
    "glb_centered": True,
    "original_center_mm": mobile_center_mm.tolist(),
    "extent_mm": mobile_extent_mm.tolist(),
    "vertices": int(len(tm.vertices)),
    "triangles": int(len(tm.faces)),
}

metadata_path = OUT_DIR / "A0101_demo_metadata.json"

metadata_path.write_text(
    json.dumps(
        metadata,
        indent=2,
    )
)


print()
print("===== OUTPUT =====")
print("Full PLY   :", full_path)
print("Mobile PLY :", mobile_ply)
print("Mobile GLB :", glb_path)
print("Metadata   :", metadata_path)

print()
print("DEMO_ASSET_OK")
