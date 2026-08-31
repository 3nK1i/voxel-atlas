from pathlib import Path

import numpy as np
import trimesh


FULL_REFERENCE = Path(
    "outputs/demo/A0101/A0101_demo_mobile_mm.ply"
)

OPEN_SOURCE = Path(
    "outputs/webxr/A0101/A0101_premium_open_mm.ply"
)

OUTPUT = Path(
    "outputs/webxr/A0101/A0101_premium_open_canonical_m.glb"
)


def load_mesh(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(
        path,
        force="mesh",
        process=False,
    )

    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(
            f"{path} did not load as a Trimesh"
        )

    return mesh.copy()


def main() -> None:
    if not FULL_REFERENCE.exists():
        raise FileNotFoundError(FULL_REFERENCE)

    if not OPEN_SOURCE.exists():
        raise FileNotFoundError(OPEN_SOURCE)

    print("===== A0101 OPEN SKULL CANONICALIZATION =====")
    print("Full reference :", FULL_REFERENCE)
    print("Open source    :", OPEN_SOURCE)
    print()

    full = load_mesh(FULL_REFERENCE)
    opened = load_mesh(OPEN_SOURCE)

    #
    # IMPORTANT:
    # Use the FULL skull bounding-box centre as the canonical
    # anatomical origin for BOTH Full and Open models.
    #
    full_bounds = np.asarray(full.bounds, dtype=np.float64)

    reference_center_mm = (
        full_bounds[0] + full_bounds[1]
    ) / 2.0

    print(
        "Canonical centre mm:",
        np.round(reference_center_mm, 6)
    )

    vertices = np.asarray(
        opened.vertices,
        dtype=np.float64,
    )

    #
    # 1. Centre relative to the FULL skull.
    #
    vertices = (
        vertices -
        reference_center_mm
    )

    #
    # 2. Medical/PyVista Z-up → glTF/WebXR Y-up.
    #
    # X_gltf =  X_medical
    # Y_gltf =  Z_medical
    # Z_gltf = -Y_medical
    #
    transformed = np.empty_like(vertices)

    transformed[:, 0] = vertices[:, 0]
    transformed[:, 1] = vertices[:, 2]
    transformed[:, 2] = -vertices[:, 1]

    #
    # 3. Millimetres → metres.
    #
    transformed *= 0.001

    opened.vertices = transformed

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    scene = trimesh.Scene(opened)
    scene.export(OUTPUT)

    bounds = np.asarray(
        scene.bounds,
        dtype=np.float64,
    )

    extent = bounds[1] - bounds[0]
    center = (bounds[0] + bounds[1]) / 2.0

    print()
    print("Output        :", OUTPUT)
    print(
        "Vertices      :",
        f"{len(opened.vertices):,}"
    )
    print(
        "Triangles     :",
        f"{len(opened.faces):,}"
    )
    print(
        "Bounds center :",
        np.round(center, 6),
        "m"
    )
    print(
        "Extent        :",
        np.round(extent, 6),
        "m"
    )

    print()
    print("OPEN_CANONICALIZATION_OK")


if __name__ == "__main__":
    main()
