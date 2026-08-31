from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh


SOURCE = Path(
    "data/mug500/A0101/A0101_clear.stl"
)

OUT_DIR = Path(
    "outputs/demo/A0101/oval_cutaway_candidates"
)

TARGET_TRIANGLES = 250_000

# Ellipsoidal cutters.
#
# The cutter is positioned ABOVE the skull and intersects only
# the superior cranium. This produces a localized rounded/oval
# opening instead of a full horizontal slice.
#
# rx, ry = opening footprint
# z_offset = cutter centre above superior skull
# rz = cutter depth
#
CANDIDATES = {
    "large": {
        "rx": 58.0,
        "ry": 70.0,
        "z_offset": 20.0,
        "rz": 80.0,
    },
    "medium": {
        "rx": 52.0,
        "ry": 62.0,
        "z_offset": 24.0,
        "rz": 72.0,
    },
    "small": {
        "rx": 46.0,
        "ry": 54.0,
        "z_offset": 26.0,
        "rz": 65.0,
    },
}

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def load_mesh(path: Path) -> trimesh.Trimesh:
    obj = trimesh.load(
        path,
        force="mesh",
        process=False,
    )

    if not isinstance(obj, trimesh.Trimesh):
        raise RuntimeError(
            f"Could not load mesh: {path}"
        )

    obj.remove_unreferenced_vertices()

    return obj


def find_superior_center(
    mesh: trimesh.Trimesh,
) -> np.ndarray:
    """
    Estimate the XY centre of the superior cranial dome.

    Using the actual superior vertices is more robust than
    assuming the skull is perfectly centred at (0, 0).
    """
    vertices = np.asarray(
        mesh.vertices,
        dtype=np.float64,
    )

    z_max = float(
        vertices[:, 2].max()
    )

    superior = vertices[
        vertices[:, 2] >= z_max - 25.0
    ]

    if len(superior) < 100:
        raise RuntimeError(
            "Not enough superior vertices to estimate cranial centre."
        )

    return np.median(
        superior[:, :2],
        axis=0,
    )


def apply_ellipsoid_opening(
    mesh: trimesh.Trimesh,
    *,
    cx: float,
    cy: float,
    cz: float,
    rx: float,
    ry: float,
    rz: float,
) -> tuple[trimesh.Trimesh, int]:
    """
    Remove surface triangles whose centres lie inside a superior
    ellipsoidal cutter.

    Because this removes the actual cranial surface rather than
    clipping the entire skull with a plane, the resulting opening
    has a localized rounded/oval boundary.

    The surface remains intentionally OPEN.
    """
    centres = np.asarray(
        mesh.triangles_center,
        dtype=np.float64,
    )

    score = (
        ((centres[:, 0] - cx) / rx) ** 2
        + ((centres[:, 1] - cy) / ry) ** 2
        + ((centres[:, 2] - cz) / rz) ** 2
    )

    remove = score <= 1.0

    removed_faces = int(
        np.count_nonzero(remove)
    )

    if removed_faces == 0:
        raise RuntimeError(
            "Ellipsoidal cutter did not intersect the skull."
        )

    remaining_faces = np.asarray(
        mesh.faces[~remove],
        dtype=np.int64,
    )

    result = trimesh.Trimesh(
        vertices=np.asarray(
            mesh.vertices,
            dtype=np.float64,
        ).copy(),
        faces=remaining_faces,
        process=False,
    )

    result.remove_unreferenced_vertices()

    return result, removed_faces


def trimesh_to_pyvista(
    mesh: trimesh.Trimesh,
) -> pv.PolyData:
    faces = np.column_stack(
        (
            np.full(
                len(mesh.faces),
                3,
                dtype=np.int64,
            ),
            np.asarray(
                mesh.faces,
                dtype=np.int64,
            ),
        )
    ).ravel()

    poly = pv.PolyData(
        np.asarray(
            mesh.vertices,
            dtype=np.float64,
        ),
        faces,
    )

    return (
        poly
        .triangulate()
        .clean()
    )


def optimize_preview(
    mesh: trimesh.Trimesh,
) -> pv.PolyData:
    poly = trimesh_to_pyvista(
        mesh
    )

    if poly.n_cells > TARGET_TRIANGLES:
        reduction = 1.0 - (
            TARGET_TRIANGLES
            / float(poly.n_cells)
        )

        reduction = float(
            np.clip(
                reduction,
                0.0,
                0.98,
            )
        )

        poly = poly.decimate(
            target_reduction=reduction,
        ).clean()

    poly = poly.compute_normals(
        point_normals=True,
        cell_normals=False,
        split_vertices=False,
        consistent_normals=True,
        inplace=False,
    )

    return poly


mesh = load_mesh(
    SOURCE
)

bounds = mesh.bounds

z_min = float(
    bounds[0, 2]
)

z_max = float(
    bounds[1, 2]
)

center_xy = find_superior_center(
    mesh
)

cx = float(center_xy[0])
cy = float(center_xy[1])

print(
    "===== A0101 OVAL CRANIAL OPENING ====="
)

print(
    "Source              :",
    SOURCE,
)

print(
    "Source vertices     :",
    f"{len(mesh.vertices):,}",
)

print(
    "Source triangles    :",
    f"{len(mesh.faces):,}",
)

print(
    "Skull Z             :",
    f"{z_min:.3f} -> {z_max:.3f} mm",
)

print(
    "Superior centre XY  :",
    f"({cx:.3f}, {cy:.3f}) mm",
)

print()


for name, params in CANDIDATES.items():
    cz = (
        z_max
        + params["z_offset"]
    )

    cut, removed = apply_ellipsoid_opening(
        mesh,
        cx=cx,
        cy=cy,
        cz=cz,
        rx=params["rx"],
        ry=params["ry"],
        rz=params["rz"],
    )

    preview = optimize_preview(
        cut
    )

    output = (
        OUT_DIR
        / f"A0101_oval_{name}_preview_mm.ply"
    )

    preview.save(
        output
    )

    removed_percent = (
        100.0
        * removed
        / len(mesh.faces)
    )

    b = preview.bounds

    print(
        f"===== {name.upper()} OVAL ====="
    )

    print(
        "Ellipse radii XY    :",
        f"{params['rx']:.1f} x "
        f"{params['ry']:.1f} mm",
    )

    print(
        "Cutter centre Z     :",
        f"{cz:.3f} mm",
    )

    print(
        "Cutter radius Z     :",
        f"{params['rz']:.1f} mm",
    )

    print(
        "Removed triangles   :",
        f"{removed:,}",
        f"({removed_percent:.2f}%)",
    )

    print(
        "Preview vertices    :",
        f"{preview.n_points:,}",
    )

    print(
        "Preview triangles   :",
        f"{preview.n_cells:,}",
    )

    print(
        "Result Z            :",
        f"{b.z_min:.3f} -> "
        f"{b.z_max:.3f} mm",
    )

    print(
        "Output              :",
        output,
    )

    print()


print(
    "OVAL_CUTAWAY_CANDIDATES_OK"
)
