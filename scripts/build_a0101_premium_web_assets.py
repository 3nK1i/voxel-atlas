from pathlib import Path
import json
import shutil

import numpy as np
import pyvista as pv
import trimesh


FULL_PLY_SRC = Path("outputs/demo/A0101/A0101_demo_mobile_mm.ply")
FULL_GLB_SRC = Path("outputs/demo/A0101/A0101_demo_mobile_m.glb")

OPEN_PLY_SRC = Path(
    "outputs/demo/A0101/oval_cutaway_candidates/"
    "A0101_oval_medium_preview_mm.ply"
)

OUT_DIR = Path("outputs/webxr/A0101")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extent_from_bounds(bounds) -> np.ndarray:
    return np.array(
        [
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4],
        ],
        dtype=float,
    )


def export_glb_from_mm_mesh(mesh_path_mm: Path, out_glb_m: Path) -> tuple[int, int, np.ndarray]:
    mesh = trimesh.load(mesh_path_mm, force="mesh", process=False)

    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"{mesh_path_mm} did not load as a Trimesh")

    mesh = mesh.copy()
    vertices = len(mesh.vertices)
    triangles = len(mesh.faces)
    extent_mm = mesh.extents.copy()

    mesh.apply_scale(0.001)  # mm -> m for GLB
    scene = trimesh.Scene(mesh)
    scene.export(out_glb_m)

    return vertices, triangles, extent_mm


def main() -> None:
    if not FULL_PLY_SRC.exists():
        raise FileNotFoundError(FULL_PLY_SRC)
    if not FULL_GLB_SRC.exists():
        raise FileNotFoundError(FULL_GLB_SRC)
    if not OPEN_PLY_SRC.exists():
        raise FileNotFoundError(OPEN_PLY_SRC)

    print("===== A0101 PREMIUM WEBXR ASSETS =====")
    print("Full source :", FULL_PLY_SRC)
    print("Open source :", OPEN_PLY_SRC)
    print()

    full_ply_out = OUT_DIR / "A0101_premium_full_mm.ply"
    full_glb_out = OUT_DIR / "A0101_premium_full_m.glb"

    open_ply_out = OUT_DIR / "A0101_premium_open_mm.ply"
    open_glb_out = OUT_DIR / "A0101_premium_open_m.glb"

    shutil.copy2(FULL_PLY_SRC, full_ply_out)
    shutil.copy2(FULL_GLB_SRC, full_glb_out)

    full_mesh = pv.read(full_ply_out)
    full_bounds = full_mesh.bounds
    full_extent_mm = extent_from_bounds(full_bounds)

    print("FULL")
    print("  vertices    :", f"{int(full_mesh.n_points):,}")
    print("  triangles   :", f"{int(full_mesh.n_cells):,}")
    print("  extent mm   :", np.round(full_extent_mm, 3))
    print()

    open_mesh = pv.read(OPEN_PLY_SRC)
    open_mesh = open_mesh.clean()

    if not open_mesh.is_all_triangles:
        open_mesh = open_mesh.triangulate()

    open_mesh = open_mesh.smooth(
        n_iter=20,
        relaxation_factor=0.03,
        boundary_smoothing=False,
        feature_smoothing=False,
    )
    open_mesh.save(open_ply_out, binary=True)

    open_vertices, open_triangles, open_extent_mm = export_glb_from_mm_mesh(
        open_ply_out,
        open_glb_out,
    )

    print("OPEN / MEDIUM OVAL")
    print("  vertices    :", f"{open_vertices:,}")
    print("  triangles   :", f"{open_triangles:,}")
    print("  extent mm   :", np.round(open_extent_mm, 3))
    print()

    metadata = {
        "case_id": "A0101",
        "dataset": "MUG500+",
        "source_reference": "A0101_clear.stl",
        "full_asset": {
            "ply_mm": str(full_ply_out),
            "glb_m": str(full_glb_out),
            "triangles": int(full_mesh.n_cells),
            "vertices": int(full_mesh.n_points),
            "extent_mm": np.round(full_extent_mm, 4).tolist(),
        },
        "open_asset": {
            "style": "medium_oval_cutaway",
            "ply_mm": str(open_ply_out),
            "glb_m": str(open_glb_out),
            "triangles": int(open_triangles),
            "vertices": int(open_vertices),
            "extent_mm": np.round(open_extent_mm, 4).tolist(),
        },
    }

    metadata_path = OUT_DIR / "A0101_premium_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print("===== OUTPUT =====")
    print("Full PLY   :", full_ply_out)
    print("Full GLB   :", full_glb_out)
    print("Open PLY   :", open_ply_out)
    print("Open GLB   :", open_glb_out)
    print("Metadata   :", metadata_path)
    print()
    print("PREMIUM_WEBXR_ASSETS_OK")


if __name__ == "__main__":
    main()
