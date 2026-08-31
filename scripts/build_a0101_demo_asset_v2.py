from pathlib import Path
import json

import numpy as np
import pyvista as pv
import trimesh
from trimesh.visual.material import PBRMaterial


SOURCE = Path(
    "data/mug500/A0101/A0101_clear.stl"
)

OUT_DIR = Path(
    "outputs/demo/A0101"
)

TARGET_TRIANGLES = 200_000

OUT_DIR.mkdir(parents=True, exist_ok=True)


print("===== A0101 DEMO ASSET V2 =====")
print("Source:", SOURCE)

mesh = pv.read(SOURCE)
mesh = mesh.triangulate().clean()

print()
print("===== SOURCE =====")
print("Vertices  :", f"{mesh.n_points:,}")
print("Triangles :", f"{mesh.n_cells:,}")


# ------------------------------------------------------------
# Mobile decimation
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# Smooth point normals
#
# Geometry stays exactly where it is. We improve only shading.
# ------------------------------------------------------------

mobile = mobile.compute_normals(
    point_normals=True,
    cell_normals=False,
    split_vertices=False,
    consistent_normals=True,
    inplace=False,
)

if "Normals" not in mobile.point_data:
    raise RuntimeError(
        "Point-normal generation failed."
    )


print()
print("===== MOBILE GEOMETRY =====")
print("Vertices  :", f"{mobile.n_points:,}")
print("Triangles :", f"{mobile.n_cells:,}")

bounds = mobile.bounds

extent_mm = np.array([
    bounds.x_max - bounds.x_min,
    bounds.y_max - bounds.y_min,
    bounds.z_max - bounds.z_min,
])

print("Extent mm :", np.round(extent_mm, 3))


# Keep desktop/mobile PLY evidence in medical millimetres.
mobile_ply = (
    OUT_DIR / "A0101_demo_mobile_v2_mm.ply"
)
mobile.save(mobile_ply)


# ------------------------------------------------------------
# Convert PolyData -> trimesh
# ------------------------------------------------------------

faces = mobile.faces.reshape(-1, 4)

if not np.all(faces[:, 0] == 3):
    raise RuntimeError(
        "Expected triangular mesh."
    )

vertices_mm = np.asarray(
    mobile.points,
    dtype=np.float64,
)

normals_medical = np.asarray(
    mobile.point_data["Normals"],
    dtype=np.float64,
)

triangles = np.asarray(
    faces[:, 1:4],
    dtype=np.int64,
)


# ------------------------------------------------------------
# Center model.
# ------------------------------------------------------------

center_mm = vertices_mm.mean(axis=0)

centered_mm = (
    vertices_mm - center_mm
)


# ------------------------------------------------------------
# Medical/PyVista coordinates are Z-up.
# glTF/WebXR coordinates are Y-up.
#
# X_gltf =  X_medical
# Y_gltf =  Z_medical
# Z_gltf = -Y_medical
# ------------------------------------------------------------

vertices_gltf_mm = np.column_stack(
    (
        centered_mm[:, 0],
        centered_mm[:, 2],
        -centered_mm[:, 1],
    )
)

normals_gltf = np.column_stack(
    (
        normals_medical[:, 0],
        normals_medical[:, 2],
        -normals_medical[:, 1],
    )
)

normal_lengths = np.linalg.norm(
    normals_gltf,
    axis=1,
)

valid = normal_lengths > 1e-12

normals_gltf[valid] /= (
    normal_lengths[valid, None]
)

vertices_m = (
    vertices_gltf_mm / 1000.0
)


tm = trimesh.Trimesh(
    vertices=vertices_m,
    faces=triangles,
    vertex_normals=normals_gltf,
    process=False,
)

tm.remove_unreferenced_vertices()


# ------------------------------------------------------------
# Professional cool medical silver/blue PBR material.
#
# Keep this opaque for V2A.
# Transparency/holographic mode comes next.
# ------------------------------------------------------------

material = PBRMaterial(
    name="Medical Silver Blue",
    baseColorFactor=[
        105,
        140,
        160,
        255,
    ],
    metallicFactor=0.05,
    roughnessFactor=0.68,
    doubleSided=True,
)

tm.visual = trimesh.visual.TextureVisuals(
    material=material
)


# ------------------------------------------------------------
# Export
# ------------------------------------------------------------

glb_path = (
    OUT_DIR / "A0101_demo_mobile_m.glb"
)

glb_path.write_bytes(
    tm.export(file_type="glb")
)


metadata = {
    "source": str(SOURCE),
    "source_units": "millimetres",
    "glb_units": "metres",
    "glb_centered": True,
    "source_coordinate_system": "Z-up",
    "glb_coordinate_system": "Y-up",
    "smooth_vertex_normals": True,
    "material": {
        "name": "Medical Silver Blue",
        "base_color_rgba": [
            105,
            140,
            160,
            255,
        ],
        "metallic": 0.05,
        "roughness": 0.68,
        "alpha_mode": "OPAQUE",
    },
    "extent_mm": extent_mm.tolist(),
    "vertices": int(len(tm.vertices)),
    "triangles": int(len(tm.faces)),
}

metadata_path = (
    OUT_DIR / "A0101_demo_metadata.json"
)

metadata_path.write_text(
    json.dumps(
        metadata,
        indent=2,
    )
)


print()
print("===== OUTPUT =====")
print("Mobile PLY :", mobile_ply)
print("Mobile GLB :", glb_path)
print("Metadata   :", metadata_path)

print()
print("Material   : Medical Silver Blue")
print("Normals    : smooth vertex normals")
print("GLB        : Y-up / metres")

print()
print("DEMO_ASSET_V2_OK")
