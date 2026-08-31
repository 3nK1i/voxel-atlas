from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyvista as pv
import SimpleITK as sitk
import trimesh


def load_dicom_series(dicom_dir: Path) -> sitk.Image:
    reader = sitk.ImageSeriesReader()

    series_ids = reader.GetGDCMSeriesIDs(str(dicom_dir))
    if not series_ids:
        raise RuntimeError(f"No DICOM series found in {dicom_dir}")

    if len(series_ids) != 1:
        raise RuntimeError(
            f"Expected exactly one DICOM series, found {len(series_ids)}"
        )

    files = reader.GetGDCMSeriesFileNames(
        str(dicom_dir),
        series_ids[0],
    )

    reader.SetFileNames(files)
    return reader.Execute()


def build_bone_mask(
    image: sitk.Image,
    threshold_hu: int,
    minimum_component_voxels: int,
) -> sitk.Image:
    # CT bone candidate mask.
    mask = sitk.BinaryThreshold(
        image,
        lowerThreshold=threshold_hu,
        upperThreshold=32767,
        insideValue=1,
        outsideValue=0,
    )

    # Mild closing helps bridge tiny threshold gaps without aggressively
    # altering anatomy.
    mask = sitk.BinaryMorphologicalClosing(
        mask,
        kernelRadius=[1, 1, 1],
        kernelType=sitk.sitkBall,
        foregroundValue=1,
    )

    # Remove small disconnected high-density structures/noise.
    cc = sitk.ConnectedComponent(mask)
    relabeled = sitk.RelabelComponent(
        cc,
        minimumObjectSize=minimum_component_voxels,
        sortByObjectSize=True,
    )

    # Keep all components that survived minimumObjectSize.
    cleaned = sitk.Cast(relabeled > 0, sitk.sitkUInt8)
    cleaned.CopyInformation(image)

    return cleaned


def sitk_mask_to_pyvista(mask: sitk.Image) -> pv.PolyData:
    array = sitk.GetArrayFromImage(mask)  # z, y, x

    # PyVista ImageData expects x,y,z indexing.
    volume = np.transpose(array, (2, 1, 0))

    grid = pv.ImageData(
        dimensions=volume.shape,
        spacing=mask.GetSpacing(),
        origin=mask.GetOrigin(),
    )

    # VTK point ordering uses Fortran order for x-fastest ImageData.
    grid.point_data["mask"] = volume.ravel(order="F")

    surface = grid.contour(
        isosurfaces=[0.5],
        scalars="mask",
        method="flying_edges",
    )

    # This series has identity direction, confirmed during inspection.
    # For a future generic implementation we will explicitly apply arbitrary
    # DICOM direction matrices here.

    surface = surface.clean()

    return surface


def smooth_and_decimate(
    surface: pv.PolyData,
    reduction: float,
) -> pv.PolyData:
    smoothed = surface.smooth_taubin(
        n_iter=30,
        pass_band=0.08,
        normalize_coordinates=True,
    )

    if 0.0 < reduction < 1.0 and smoothed.n_cells > 1000:
        smoothed = smoothed.decimate_pro(
            reduction,
            preserve_topology=True,
        )

    return smoothed.clean()


def export_glb(mesh: pv.PolyData, output_path: Path) -> None:
    faces = mesh.faces.reshape(-1, 4)

    if not np.all(faces[:, 0] == 3):
        raise RuntimeError("Expected a triangular mesh.")

    tm = trimesh.Trimesh(
        vertices=np.asarray(mesh.points),
        faces=np.asarray(faces[:, 1:4]),
        process=False,
    )

    tm.remove_unreferenced_vertices()

    output_path.write_bytes(tm.export(file_type="glb"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a skull mesh from a head CT DICOM series."
    )

    parser.add_argument(
        "--dicom-dir",
        type=Path,
        default=Path("data/dicom"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
    )
    parser.add_argument(
        "--bone-threshold",
        type=int,
        default=300,
        help="Initial CT bone threshold in HU.",
    )
    parser.add_argument(
        "--minimum-component-voxels",
        type=int,
        default=100,
        help="Discard connected components smaller than this.",
    )
    parser.add_argument(
        "--reduction",
        type=float,
        default=0.65,
        help="Fraction of triangles to remove from the clean mesh.",
    )
    parser.add_argument(
        "--no-viewer",
        action="store_true",
    )

    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("===== SKULL RECONSTRUCTION =====")
    print(f"DICOM directory     : {args.dicom_dir}")
    print(f"Bone threshold      : {args.bone_threshold} HU")

    image = load_dicom_series(args.dicom_dir)

    print()
    print("===== CT VOLUME =====")
    print(f"Size                : {image.GetSize()}")
    print(f"Spacing (mm)        : {image.GetSpacing()}")
    print(f"Origin              : {image.GetOrigin()}")

    mask = build_bone_mask(
        image,
        threshold_hu=args.bone_threshold,
        minimum_component_voxels=args.minimum_component_voxels,
    )

    mask_array = sitk.GetArrayFromImage(mask)

    print()
    print("===== BONE MASK =====")
    print(f"Bone voxels         : {int(mask_array.sum()):,}")
    print(
        f"Bone fraction       : "
        f"{100.0 * mask_array.mean():.3f}%"
    )

    print()
    print("===== SURFACE EXTRACTION =====")

    raw_mesh = sitk_mask_to_pyvista(mask)

    if raw_mesh.n_points == 0 or raw_mesh.n_cells == 0:
        raise RuntimeError(
            "Surface extraction produced an empty mesh. "
            "Try lowering --bone-threshold."
        )

    print(f"Raw vertices        : {raw_mesh.n_points:,}")
    print(f"Raw triangles       : {raw_mesh.n_cells:,}")

    raw_path = args.output_dir / "skull_raw.ply"
    raw_mesh.save(raw_path)

    clean_mesh = smooth_and_decimate(
        raw_mesh,
        reduction=args.reduction,
    )

    print(f"Clean vertices      : {clean_mesh.n_points:,}")
    print(f"Clean triangles     : {clean_mesh.n_cells:,}")

    bounds = clean_mesh.bounds

    extent_x = bounds.x_max - bounds.x_min
    extent_y = bounds.y_max - bounds.y_min
    extent_z = bounds.z_max - bounds.z_min

    print()
    print("===== PHYSICAL MESH EXTENT =====")
    print(f"X                   : {extent_x:.2f} mm")
    print(f"Y                   : {extent_y:.2f} mm")
    print(f"Z                   : {extent_z:.2f} mm")

    clean_path = args.output_dir / "skull_clean.ply"
    glb_path = args.output_dir / "skull.glb"

    clean_mesh.save(clean_path)
    export_glb(clean_mesh, glb_path)

    print()
    print("===== OUTPUT =====")
    print(f"Raw PLY             : {raw_path}")
    print(f"Clean PLY           : {clean_path}")
    print(f"GLB                 : {glb_path}")

    if not args.no_viewer:
        print()
        print("Opening interactive viewer...")
        print("Close the PyVista window to return to the terminal.")

        plotter = pv.Plotter(
            window_size=(1100, 850),
            title="Patient-Specific CT Skull",
        )

        plotter.add_mesh(
            clean_mesh,
            color="ivory",
            smooth_shading=True,
            specular=0.25,
        )

        plotter.add_axes()
        plotter.show_grid()
        plotter.reset_camera()
        plotter.show()

    print()
    print("SKULL_RECONSTRUCTION_OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
