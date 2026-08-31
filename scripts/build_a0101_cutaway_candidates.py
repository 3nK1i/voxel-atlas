from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh


SOURCE = Path("data/mug500/A0101/A0101_clear.stl")
OUT_DIR = Path("outputs/demo/A0101/cutaway_candidates")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_TRIANGLES = 250_000

CANDIDATES = [
    ("large", 0.74),
    ("medium", 0.78),
    ("small", 0.82),
]


def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="mesh", process=False)

    if isinstance(loaded, trimesh.Scene):
        parts = tuple(loaded.geometry.values())
        if not parts:
            raise RuntimeError(f"No mesh geometry found in {path}")
        mesh = trimesh.util.concatenate(parts)
    else:
        mesh = loaded

    mesh.remove_unreferenced_vertices()
    return mesh


def trimesh_to_pv(mesh: trimesh.Trimesh) -> pv.PolyData:
    faces = np.hstack(
        [
            np.full((len(mesh.faces), 1), 3, dtype=np.int64),
            mesh.faces.astype(np.int64),
        ]
    ).ravel()

    poly = pv.PolyData(mesh.vertices, faces)
    return poly.triangulate().clean()


def pv_to_trimesh(poly: pv.PolyData) -> trimesh.Trimesh:
    poly = poly.triangulate().clean()
    faces = poly.faces.reshape(-1, 4)[:, 1:4]
    return trimesh.Trimesh(
        vertices=np.asarray(poly.points),
        faces=np.asarray(faces),
        process=False,
    )


def decimate_preview(
    mesh: trimesh.Trimesh,
    target_triangles: int,
) -> trimesh.Trimesh:
    poly = trimesh_to_pv(mesh)

    if poly.n_cells > target_triangles:
        reduction = 1.0 - (target_triangles / poly.n_cells)
        reduction = max(0.0, min(0.99, reduction))
        poly = poly.decimate(reduction)

    poly = poly.smooth(
        n_iter=20,
        relaxation_factor=0.02,
        feature_smoothing=False,
        boundary_smoothing=True,
    )

    return pv_to_trimesh(poly)


def save_preview(mesh: trimesh.Trimesh, path: Path) -> None:
    poly = trimesh_to_pv(mesh)
    poly = poly.compute_normals(
        cell_normals=False,
        point_normals=True,
        auto_orient_normals=True,
        splitting=False,
        inplace=False,
    )
    poly.save(path)


def slice_open_top(
    mesh: trimesh.Trimesh,
    keep_ratio: float,
) -> tuple[trimesh.Trimesh, float]:
    bounds = mesh.bounds
    center = bounds.mean(axis=0)

    z_min = bounds[0, 2]
    z_max = bounds[1, 2]
    height = z_max - z_min

    cut_z = z_min + keep_ratio * height

    result = trimesh.intersections.slice_mesh_plane(
        mesh,
        plane_normal=np.array([0.0, 0.0, -1.0], dtype=float),
        plane_origin=np.array([center[0], center[1], cut_z], dtype=float),
        cap=True,
    )

    if result is None or len(result.faces) == 0:
        raise RuntimeError("Cutaway slicing returned an empty mesh.")

    result.remove_unreferenced_vertices()
    return result, cut_z


def fmt(arr: np.ndarray) -> str:
    return "[" + " ".join(f"{v:.3f}" for v in arr) + "]"


def main() -> None:
    mesh = load_mesh(SOURCE)

    z_min = float(mesh.bounds[0, 2])
    z_max = float(mesh.bounds[1, 2])
    height = z_max - z_min

    print("===== A0101 CUTAWAY CANDIDATES =====")
    print("Source        :", SOURCE)
    print("Source faces  :", f"{len(mesh.faces):,}")
    print("Z min         :", f"{z_min:.3f} mm")
    print("Z max         :", f"{z_max:.3f} mm")
    print("Height        :", f"{height:.3f} mm")
    print()

    for name, keep_ratio in CANDIDATES:
        cutaway, cut_z = slice_open_top(mesh, keep_ratio)
        preview = decimate_preview(cutaway, TARGET_TRIANGLES)

        out_path = OUT_DIR / f"A0101_cutaway_{name}_preview_mm.ply"
        save_preview(preview, out_path)

        pmin = preview.bounds[0]
        pmax = preview.bounds[1]

        print(f"===== {name.upper()} OPENING =====")
        print("Retain ratio  :", f"{keep_ratio:.2f}")
        print("Cut Z         :", f"{cut_z:.3f} mm")
        print("Vertices      :", f"{len(preview.vertices):,}")
        print("Triangles     :", f"{len(preview.faces):,}")
        print("Result Z      :", f"{pmin[2]:.3f} -> {pmax[2]:.3f} mm")
        print("Output        :", out_path)
        print()

    print("CUTAWAY_CANDIDATES_OK")


if __name__ == "__main__":
    main()
