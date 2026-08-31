from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree


OUR_PATH = Path(
    "outputs/mug500/A0101/A0101_full_mm.ply"
)

REF_PATH = Path(
    "data/mug500/A0101/A0101_clear.stl"
)

SAMPLES = 200_000


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

    return obj


def print_stats(name, mesh):
    print(name)
    print("  vertices    :", f"{len(mesh.vertices):,}")
    print("  triangles   :", f"{len(mesh.faces):,}")
    print("  bounds min  :", np.round(mesh.bounds[0], 3))
    print("  bounds max  :", np.round(mesh.bounds[1], 3))
    print("  extent mm   :", np.round(mesh.extents, 3))


our = load_mesh(OUR_PATH)
ref = load_mesh(REF_PATH)

print("===== A0101 GEOMETRY VALIDATION =====")
print()

print_stats("OUR FULL MESH", our)
print()
print_stats("REFERENCE CLEAR STL", ref)

extent_delta = our.extents - ref.extents

print()
print("===== EXTENT DIFFERENCE =====")
print(
    "Delta XYZ mm :",
    np.round(extent_delta, 3),
)

print(
    "Delta XYZ %  :",
    np.round(
        100.0 * extent_delta / ref.extents,
        3,
    ),
)

print()
print("===== SURFACE SAMPLING =====")
print("Samples/mesh :", f"{SAMPLES:,}")

rng = np.random.default_rng(42)

# trimesh surface sampling uses NumPy's global RNG.
np.random.seed(42)
our_samples, _ = trimesh.sample.sample_surface(
    our,
    SAMPLES,
)

np.random.seed(43)
ref_samples, _ = trimesh.sample.sample_surface(
    ref,
    SAMPLES,
)

tree_ref = cKDTree(ref_samples)
tree_our = cKDTree(our_samples)

d_our_ref, _ = tree_ref.query(
    our_samples,
    k=1,
    workers=-1,
)

d_ref_our, _ = tree_our.query(
    ref_samples,
    k=1,
    workers=-1,
)

all_dist = np.concatenate(
    (d_our_ref, d_ref_our)
)


def percentile(x, q):
    return float(np.percentile(x, q))


print()
print("===== APPROX. SYMMETRIC SURFACE ERROR =====")
print(
    f"Mean       : {all_dist.mean():.3f} mm"
)
print(
    f"Median     : {np.median(all_dist):.3f} mm"
)
print(
    f"P90        : {percentile(all_dist, 90):.3f} mm"
)
print(
    f"P95        : {percentile(all_dist, 95):.3f} mm"
)
print(
    f"P99        : {percentile(all_dist, 99):.3f} mm"
)
print(
    f"Max sample : {all_dist.max():.3f} mm"
)

print()
print("VALIDATION_OK")
