import pyvista as pv


OUR = (
    "outputs/mug500/A0101/"
    "A0101_full_mm.ply"
)

REF = (
    "data/mug500/A0101/"
    "A0101_clear.stl"
)

our = pv.read(OUR)
ref = pv.read(REF)

plotter = pv.Plotter(
    title="A0101 — Our Mesh vs Reference",
    window_size=(1200, 900),
)

plotter.add_mesh(
    ref,
    color="white",
    opacity=0.35,
    smooth_shading=True,
    label="Reference",
)

plotter.add_mesh(
    our,
    color="orange",
    opacity=0.65,
    smooth_shading=True,
    label="Ours",
)

plotter.add_legend()
plotter.add_axes()
plotter.reset_camera()
plotter.show()
