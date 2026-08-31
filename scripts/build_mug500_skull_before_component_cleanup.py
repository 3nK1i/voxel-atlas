from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyvista as pv
import SimpleITK as sitk
import trimesh
from skimage.measure import marching_cubes


def load_binary_volume(path: Path):
    image = sitk.ReadImage(str(path))
    array = sitk.GetArrayFromImage(image)

    values = np.unique(array)
    if not np.all(np.isin(values, [0, 1])):
        raise RuntimeError(
            f"Expected a binary 0/1 segmentation, found values: {values[:20]}"
        )

    return image, array.astype(np.uint8)


def extract_surface(image: sitk.Image, mask: np.ndarray) -> pv.PolyData:
    spacing_xyz = np.asarray(image.GetSpacing(), dtype=np.float64)
    origin_xyz = np.asarray(image.GetOrigin(), dtype=np.float64)
    direction = np.asarray(image.GetDirection(), dtype=np.float64).reshape(3, 3)

    # The MUG500 segmentation touches some volume boundaries.
    # Pad with one background voxel so Marching Cubes can close the surface.
    padded = np.pad(
        mask,
        pad_width=1,
        mode="constant",
        constant_values=0,
    )

    # skimage array coordinates are Z,Y,X.
    spacing_zyx = (
        spacing_xyz[2],
        spacing_xyz[1],
        spacing_xyz[0],
    )

    vertices_zyx, faces, _, _ = marching_cubes(
        padded,
        level=0.5,
        spacing=spacing_zyx,
        allow_degenerate=False,
    )

    # Convert Z,Y,X -> X,Y,Z.
    vertices_xyz = vertices_zyx[:, [2, 1, 0]]

    # Padding inserted one voxel before the original volume.
    padded_origin = origin_xyz - direction @ spacing_xyz

    # Apply the actual medical-image direction transform.
    vertices_physical = (
        vertices_xyz @ direction.T
        + padded_origin
    )

    vtk_faces = np.column_stack(
        (
            np.full(len(faces), 3, dtype=np.int64),
            faces.astype(np.int64),
        )
    ).ravel()

    mesh = pv.PolyData(
        vertices_physical,
        vtk_faces,
    )

    return mesh.clean()


def make_full_mesh(raw: pv.PolyData) -> pv.PolyData:
    # Conservative Taubin smoothing: reduce voxel stair-stepping while
    # preserving craniofacial geometry.
    mesh = raw.smooth_taubin(
        n_iter=15,
        pass_band=0.10,
    )

    return mesh.clean()


def make_mobile_mesh(
    full: pv.PolyData,
    target_triangles: int,
) -> pv.PolyData:
    if full.n_cells <= target_triangles:
        return full.copy()

    reduction = 1.0 - (target_triangles / full.n_cells)
    reduction = float(np.clip(reduction, 0.0, 0.98))

    mesh = full.decimate_pro(
        reduction,
        preserve_topology=True,
    )

    return mesh.clean()


def export_glb_metres(mesh: pv.PolyData, path: Path) -> None:
    faces = mesh.faces.reshape(-1, 4)

    if not np.all(faces[:, 0] == 3):
        raise RuntimeError("Expected triangular PolyData.")

    # PLY/reference geometry stays in millimetres.
    # glTF/GLB is exported in metres for future WebXR/AR use.
    vertices_m = np.asarray(mesh.points, dtype=np.float64) / 1000.0
    triangles = np.asarray(faces[:, 1:4], dtype=np.int64)

    tm = trimesh.Trimesh(
        vertices=vertices_m,
        faces=triangles,
        process=False,
    )

    tm.remove_unreferenced_vertices()

    # Neutral anatomical presentation color.
    tm.visual.vertex_colors = np.tile(
        np.array([235, 232, 220, 255], dtype=np.uint8),
        (len(tm.vertices), 1),
    )

    path.write_bytes(tm.export(file_type="glb"))


def print_mesh_stats(name: str, mesh: pv.PolyData) -> None:
    b = mesh.bounds

    sx = b.x_max - b.x_min
    sy = b.y_max - b.y_min
    sz = b.z_max - b.z_min

    print(name)
    print(f"  vertices          : {mesh.n_points:,}")
    print(f"  triangles         : {mesh.n_cells:,}")
    print(f"  extent X          : {sx:.2f} mm")
    print(f"  extent Y          : {sy:.2f} mm")
    print(f"  extent Z          : {sz:.2f} mm")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/mug500/A0101/A0101.nrrd"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/mug500/A0101"),
    )
    parser.add_argument(
        "--target-triangles",
        type=int,
        default=200_000,
    )
    parser.add_argument(
        "--no-viewer",
        action="store_true",
    )

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("===== MUG500+ SKULL RECONSTRUCTION =====")
    print("Input              :", args.input)

    image, mask = load_binary_volume(args.input)

    print()
    print("===== SOURCE VOLUME =====")
    print("Size               :", image.GetSize())
    print("Spacing (mm)       :", image.GetSpacing())
    print("Origin             :", image.GetOrigin())
    print("Direction          :", image.GetDirection())
    print("Foreground voxels  :", f"{int(mask.sum()):,}")

    print()
    print("===== SURFACE EXTRACTION =====")

    raw = extract_surface(image, mask)
    full = make_full_mesh(raw)
    mobile = make_mobile_mesh(
        full,
        target_triangles=args.target_triangles,
    )

    print_mesh_stats("RAW", raw)
    print()
    print_mesh_stats("FULL / SMOOTHED", full)
    print()
    print_mesh_stats("MOBILE", mobile)

    raw_path = args.output_dir / "A0101_raw_mm.ply"
    full_path = args.output_dir / "A0101_full_mm.ply"
    mobile_path = args.output_dir / "A0101_mobile_mm.ply"
    glb_path = args.output_dir / "A0101_mobile_m.glb"

    raw.save(raw_path)
    full.save(full_path)
    mobile.save(mobile_path)
    export_glb_metres(mobile, glb_path)

    print()
    print("===== OUTPUT =====")
    print("Raw PLY            :", raw_path)
    print("Full PLY           :", full_path)
    print("Mobile PLY         :", mobile_path)
    print("Mobile GLB         :", glb_path)
    print()
    print("PLY units          : millimetres")
    print("GLB units          : metres")

    if not args.no_viewer:
        print()
        print("Opening interactive skull viewer...")
        print("Close the window to return to the terminal.")

        plotter = pv.Plotter(
            title="MUG500+ A0101 — Reconstructed Skull",
            window_size=(1200, 900),
        )

        plotter.add_mesh(
            full,
            color="ivory",
            smooth_shading=True,
            specular=0.20,
        )

        plotter.add_axes()
        plotter.reset_camera()
        plotter.show()

    print()
    print("MUG500_SKULL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
