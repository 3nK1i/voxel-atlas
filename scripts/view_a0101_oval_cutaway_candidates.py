from pathlib import Path

import pyvista as pv


ROOT = Path(
    "outputs/demo/A0101/oval_cutaway_candidates"
)

CASES = [
    (
        "Large oval",
        ROOT / "A0101_oval_large_preview_mm.ply",
    ),
    (
        "Medium oval",
        ROOT / "A0101_oval_medium_preview_mm.ply",
    ),
    (
        "Small oval",
        ROOT / "A0101_oval_small_preview_mm.ply",
    ),
]


print(
    "===== OVAL CUTAWAY VIEWER ====="
)

for title, path in CASES:
    if not path.exists():
        raise RuntimeError(
            f"Missing candidate: {path}"
        )

    print(
        f"{title:14s}: "
        f"{path.stat().st_size / 1024 / 1024:.1f} MB"
    )


plotter = pv.Plotter(
    shape=(1, 3),
    window_size=(1650, 760),
    title=(
        "A0101 — Rounded Cranial Opening Candidates"
    ),
)


for index, (title, path) in enumerate(CASES):
    mesh = pv.read(
        path
    )

    plotter.subplot(
        0,
        index,
    )

    plotter.set_background(
        "#07111a"
    )

    plotter.add_text(
        title,
        position="upper_left",
        font_size=13,
        color="white",
    )

    plotter.add_mesh(
        mesh,
        color="#9fbcca",
        smooth_shading=True,
        ambient=0.18,
        diffuse=0.78,
        specular=0.25,
        specular_power=20,
    )

    plotter.add_axes()

    plotter.reset_camera()


plotter.link_views()

# Initial oblique/front view.
plotter.subplot(
    0,
    0,
)

plotter.camera_position = [
    (225.0, -280.0, 175.0),
    (0.0, 0.0, 10.0),
    (0.0, 0.0, 1.0),
]

print()
print(
    "Rotate one view; all three are linked."
)

print(
    "Inspect both front/oblique and directly from above."
)

plotter.show()

print()
print(
    "OVAL_CUTAWAY_VIEWER_OK"
)
