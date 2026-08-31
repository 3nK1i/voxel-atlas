import pyvista as pv


REF = pv.read(
    "data/mug500/A0101/A0101_clear.stl"
)

OURS = pv.read(
    "outputs/mug500/A0101/A0101_full_mm.ply"
)

OUTLIERS = pv.read(
    "outputs/mug500/A0101/validation/"
    "ours_gt_10mm.ply"
)


plotter = pv.Plotter(
    title="A0101 — Surface Difference Inspection",
    window_size=(1200, 900),
)

plotter.add_mesh(
    REF,
    color="white",
    opacity=0.30,
    smooth_shading=True,
    label="Reference",
)

plotter.add_mesh(
    OURS,
    color="lightgray",
    opacity=0.25,
    smooth_shading=True,
    label="Ours",
)

plotter.add_points(
    OUTLIERS,
    color="red",
    point_size=5,
    render_points_as_spheres=True,
    label=">10 mm difference",
)

plotter.add_legend()
plotter.add_axes()
plotter.reset_camera()
plotter.show()
