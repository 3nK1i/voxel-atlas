from pathlib import Path

import pyvista as pv


OUT_DIR = Path("outputs/demo/A0101/cutaway_candidates")

CASES = [
    ("Large opening", OUT_DIR / "A0101_cutaway_large_preview_mm.ply"),
    ("Medium opening", OUT_DIR / "A0101_cutaway_medium_preview_mm.ply"),
    ("Small opening", OUT_DIR / "A0101_cutaway_small_preview_mm.ply"),
]


def main() -> None:
    print("===== CUTAWAY VIEWER =====")

    for title, path in CASES:
        if not path.exists():
            raise FileNotFoundError(path)
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"{title:<16}: {size_mb:.1f} MB")

    print()
    print("Opening comparison viewer...")
    print("Rotate one viewport and all three should follow.")
    print()

    plotter = pv.Plotter(
        shape=(1, 3),
        window_size=(1800, 900),
        title="A0101 — Open-Top Cutaway Candidates",
        border=True,
    )

    bg = "#02111d"
    mesh_color = "#bfd5e2"

    meshes = []

    for idx, (title, path) in enumerate(CASES):
        mesh = pv.read(path)
        meshes.append(mesh)

        plotter.subplot(0, idx)
        plotter.set_background(bg)

        plotter.add_text(
            title,
            position="upper_left",
            font_size=14,
            color="white",
        )

        plotter.add_mesh(
            mesh,
            color=mesh_color,
            smooth_shading=True,
            ambient=0.18,
            diffuse=0.80,
            specular=0.30,
            specular_power=18.0,
        )

        plotter.add_axes(line_width=2)
        plotter.show_grid(color="white", font_size=8)

    plotter.link_views()

    # Good default oblique angle for all subplots
    plotter.subplot(0, 0)
    plotter.camera_position = [
        (230.0, -260.0, 170.0),  # camera
        (0.0, 0.0, 10.0),        # focal point
        (0.0, 0.0, 1.0),         # up vector
    ]

    print("CUTAWAY_VIEWER_OK")
    plotter.show()


if __name__ == "__main__":
    main()
