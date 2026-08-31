from pathlib import Path

import numpy as np
import pyvista as pv
import trimesh
from scipy.spatial import cKDTree


OUR_PATH = Path(
    "outputs/mug500/A0101/A0101_full_mm.ply"
)
REF_PATH = Path(
    "data/mug500/A0101/A0101_clear.stl"
)

OUTPUT_DIR = Path(
    "outputs/mug500/A0101/validation"
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = 400_000


def load(path):
    mesh = trimesh.load(
        path,
        force="mesh",
        process=False,
    )
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError(f"Failed to load {path}")
    return mesh


def stats(name, distances):
    print(name)
    print(f"  mean   : {distances.mean():.3f} mm")
    print(f"  median : {np.median(distances):.3f} mm")

    for q in (90, 95, 99):
        print(
            f"  P{q:<2}    : "
            f"{np.percentile(distances, q):.3f} mm"
        )

    print(f"  max    : {distances.max():.3f} mm")


def report_outliers(
    name,
    points,
    distances,
    threshold,
):
    keep = distances > threshold
    p = points[keep]

    print()
    print(
        f"{name} > {threshold:g} mm: "
        f"{len(p):,} / {len(points):,} "
        f"({100.0 * len(p) / len(points):.3f}%)"
    )

    if not len(p):
        return None

    print(
        "  bbox min :",
        np.round(p.min(axis=0), 3),
    )
    print(
        "  bbox max :",
        np.round(p.max(axis=0), 3),
    )
    print(
        "  centroid :",
        np.round(p.mean(axis=0), 3),
    )

    return p


our = load(OUR_PATH)
ref = load(REF_PATH)

np.random.seed(100)
our_pts, _ = trimesh.sample.sample_surface(
    our,
    SAMPLES,
)

np.random.seed(101)
ref_pts, _ = trimesh.sample.sample_surface(
    ref,
    SAMPLES,
)

tree_ref = cKDTree(ref_pts)
tree_our = cKDTree(our_pts)

our_to_ref, _ = tree_ref.query(
    our_pts,
    workers=-1,
)

ref_to_our, _ = tree_our.query(
    ref_pts,
    workers=-1,
)

print("===== DIRECTED SURFACE VALIDATION =====")
print()

stats("OURS -> REFERENCE", our_to_ref)
print()
stats("REFERENCE -> OURS", ref_to_our)

saved = {}

for threshold in (5.0, 10.0, 20.0, 40.0):
    pts = report_outliers(
        "OURS -> REF",
        our_pts,
        our_to_ref,
        threshold,
    )

    if pts is not None:
        saved[f"ours_gt_{int(threshold)}mm"] = pts

print()
print("===== REFERENCE OUTLIERS =====")

for threshold in (5.0, 10.0, 20.0, 40.0):
    report_outliers(
        "REF -> OURS",
        ref_pts,
        ref_to_our,
        threshold,
    )

# Save our outlier point clouds for interactive inspection.
for name, points in saved.items():
    cloud = pv.PolyData(points)

    path = OUTPUT_DIR / f"{name}.ply"
    cloud.save(path)

    print("Saved:", path)

print()
print("OUTLIER_DIAGNOSTIC_OK")
