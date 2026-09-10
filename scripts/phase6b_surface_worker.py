#!/usr/bin/env python3
from __future__ import annotations

import argparse
from itertools import combinations
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite
import os
from pathlib import Path
import platform
import struct
import sys


SCHEMA_VERSION = 2
MAGIC = b"VXSF"
HEADER = struct.Struct("<4s8I")
FLAGS = 1
OPERATION = "refine_accurate_surface"
REFINEMENT = "bounded_taubin_vertex_clustering"
REFINEMENT_ALGORITHM_VERSION = 2
SMOOTHING_ITERATIONS = 2
TAUBIN_LAMBDA = 0.33
TAUBIN_MU = -0.34
SMOOTHING_DISPLACEMENT_FRACTION = 0.25
TOTAL_DISPLACEMENT_FRACTION = 0.80
MIN_TRIANGLE_RETENTION_RATIO = 0.70
CLUSTER_CELL_SIZES_INDEX = (0.50, 0.65, 0.70, 0.80)
LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES = 12
LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES = 6
LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION = 0.0001
LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION = 0.0001


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_regular_file(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"{field} must be an absolute regular file")
    return path.resolve(strict=True)


def absolute_output(value: str, field: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or path.exists():
        raise ValueError(f"{field} must be a new absolute non-symlink path")
    resolved = path.resolve(strict=False)
    if resolved.parent.is_symlink() or not resolved.parent.is_dir():
        raise ValueError(f"{field} parent is unsafe")
    return resolved


def positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} is invalid")
    return value


def finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise ValueError(f"{field} is invalid")
    return float(value)


def runtime_identity() -> dict[str, str]:
    payload = {
        "schema_version": 1,
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scikit_image_version": importlib.metadata.version("scikit-image"),
        "marching_cubes_available": True,
    }
    fingerprint = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "python_version": payload["python_version"],
        "numpy_version": payload["numpy_version"],
        "scikit_image_version": payload["scikit_image_version"],
        "runtime_fingerprint_sha256": fingerprint,
    }


def load_request(path: Path) -> dict[str, object]:
    request = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(request, dict)
        or request.get("schema_version") != SCHEMA_VERSION
        or request.get("operation") != OPERATION
        or request.get("refinement") != REFINEMENT
        or request.get("refinement_algorithm_version") != REFINEMENT_ALGORITHM_VERSION
        or request.get("source_label_map") != "immutable"
        or request.get("clinical_validation") != "not_claimed"
    ):
        raise ValueError("surface refinement request contract is invalid")
    positive_int(request.get("label_id"), "label id")
    for key in ("reference_surface_sha256", "expected_runtime_fingerprint_sha256"):
        value = request.get(key)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"{key} is invalid")
    reference_id = request.get("reference_surface_id")
    if (
        not isinstance(reference_id, str)
        or len(reference_id) != 37
        or not reference_id.startswith("surf-")
        or any(character not in "0123456789abcdef" for character in reference_id[5:])
    ):
        raise ValueError("reference surface id is invalid")
    affine = request.get("array_index_to_patient_lps")
    if not isinstance(affine, list) or len(affine) != 4:
        raise ValueError("Patient LPS affine is invalid")
    for row in affine:
        if (
            not isinstance(row, list)
            or len(row) != 4
            or any(
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not isfinite(float(item))
                for item in row
            )
        ):
            raise ValueError("Patient LPS affine is invalid")
    if [float(item) for item in affine[3]] != [0.0, 0.0, 0.0, 1.0]:
        raise ValueError("Patient LPS affine is invalid")
    shape = request.get("shape")
    if (
        not isinstance(shape, list)
        or len(shape) != 3
        or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in shape)
    ):
        raise ValueError("canonical volume shape is invalid")
    positive_int(request.get("max_vertices"), "max_vertices")
    positive_int(request.get("max_triangles"), "max_triangles")
    positive_int(request.get("max_payload_bytes"), "max_payload_bytes")
    policy = request.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("surface refinement policy is invalid")
    expected_policy = {
        "smoothing_iterations": SMOOTHING_ITERATIONS,
        "taubin_lambda": TAUBIN_LAMBDA,
        "taubin_mu": TAUBIN_MU,
        "smoothing_displacement_fraction": SMOOTHING_DISPLACEMENT_FRACTION,
        "total_displacement_fraction": TOTAL_DISPLACEMENT_FRACTION,
        "minimum_triangle_retention_ratio": MIN_TRIANGLE_RETENTION_RATIO,
        "cluster_cell_sizes_index": list(CLUSTER_CELL_SIZES_INDEX),
        "local_topology_repair_max_candidate_faces": LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES,
        "local_topology_repair_max_removed_faces": LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES,
        "local_topology_repair_max_removed_face_fraction": LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION,
        "local_topology_repair_max_removed_area_fraction": LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION,
        "require_closed_edge_manifold": True,
        "require_vertex_fan_manifold": True,
    }
    if policy != expected_policy:
        raise ValueError("surface refinement policy is invalid")
    return request


def decode_surface(payload: bytes, *, label_id: int):
    import numpy as np

    if len(payload) < HEADER.size:
        raise ValueError("reference surface payload is truncated")
    try:
        magic, version, payload_label, vertex_count, index_count, pos_bytes, normal_bytes, index_bytes, flags = HEADER.unpack_from(payload)
    except struct.error as exc:
        raise ValueError("reference surface payload is invalid") from exc
    if (
        magic != MAGIC
        or version != SCHEMA_VERSION
        or payload_label != label_id
        or vertex_count <= 0
        or index_count <= 0
        or index_count % 3 != 0
        or pos_bytes != vertex_count * 3 * 4
        or normal_bytes != vertex_count * 3 * 4
        or index_bytes != index_count * 4
        or flags != FLAGS
        or len(payload) != HEADER.size + pos_bytes + normal_bytes + index_bytes
    ):
        raise ValueError("reference surface payload contract is invalid")
    offset = HEADER.size
    positions = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3).astype(np.float64)
    offset += pos_bytes
    normals = np.frombuffer(payload, dtype="<f4", count=vertex_count * 3, offset=offset).reshape(-1, 3).astype(np.float64)
    offset += normal_bytes
    faces = np.frombuffer(payload, dtype="<u4", count=index_count, offset=offset).reshape(-1, 3).astype(np.int64)
    if (
        not np.all(np.isfinite(positions))
        or not np.all(np.isfinite(normals))
        or int(faces.max()) >= vertex_count
    ):
        raise ValueError("reference surface geometry is invalid")
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths <= 1e-12) or not np.allclose(lengths, 1.0, rtol=0.0, atol=2e-5):
        raise ValueError("reference surface normals are invalid")
    return positions, normals, faces


def compact_mesh(positions, reference_normals, faces):
    import numpy as np

    if len(faces) <= 0:
        raise ValueError("surface has no triangles")
    valid = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 0] != faces[:, 2])
    )
    removed_degenerate = int(np.count_nonzero(~valid))
    faces = faces[valid]
    if len(faces) <= 0:
        raise ValueError("surface repair removed all triangles")
    triangles = positions[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    area_ok = np.linalg.norm(cross, axis=1) > 1e-12
    removed_degenerate += int(np.count_nonzero(~area_ok))
    faces = faces[area_ok]
    if len(faces) <= 0:
        raise ValueError("surface repair removed all triangles")
    canonical = np.sort(faces, axis=1)
    _, first = np.unique(canonical, axis=0, return_index=True)
    keep = np.sort(first)
    removed_duplicates = len(faces) - len(keep)
    faces = faces[keep]
    used, inverse = np.unique(faces.reshape(-1), return_inverse=True)
    removed_unreferenced = len(positions) - len(used)
    old_to_new = np.full(len(positions), -1, dtype=np.int64)
    old_to_new[used] = np.arange(len(used), dtype=np.int64)
    positions = positions[used]
    reference_normals = reference_normals[used]
    faces = inverse.reshape(-1, 3)
    return (
        positions,
        reference_normals,
        faces,
        removed_degenerate + removed_duplicates + removed_unreferenced,
        old_to_new,
        removed_unreferenced,
    )


def unique_edges_with_counts(faces):
    import numpy as np

    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    return np.unique(edges, axis=0, return_counts=True)


def edge_incidence(faces):
    import numpy as np

    face_count = len(faces)
    occurrences = np.vstack(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])
    )
    occurrences = np.sort(occurrences, axis=1)
    unique_edges, inverse, counts = np.unique(
        occurrences, axis=0, return_inverse=True, return_counts=True
    )
    face_edge_ids = inverse.reshape(3, face_count).T
    return unique_edges, counts, face_edge_ids


def _link_component_count(first, second) -> int:
    mapping: dict[int, int] = {}
    parent: list[int] = []
    rank: list[int] = []

    def local_index(value: int) -> int:
        index = mapping.get(value)
        if index is not None:
            return index
        index = len(parent)
        mapping[value] = index
        parent.append(index)
        rank.append(0)
        return index

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        root_a = find(a)
        root_b = find(b)
        if root_a == root_b:
            return
        if rank[root_a] < rank[root_b]:
            root_a, root_b = root_b, root_a
        parent[root_b] = root_a
        if rank[root_a] == rank[root_b]:
            rank[root_a] += 1

    for raw_a, raw_b in zip(first, second):
        union(local_index(int(raw_a)), local_index(int(raw_b)))
    return len({find(index) for index in range(len(parent))})


def nonmanifold_vertex_fan_count(vertex_count: int, faces) -> int:
    import numpy as np

    if vertex_count <= 0 or len(faces) <= 0:
        return 0
    owners = np.concatenate((faces[:, 0], faces[:, 1], faces[:, 2]))
    link_first = np.concatenate((faces[:, 1], faces[:, 2], faces[:, 0]))
    link_second = np.concatenate((faces[:, 2], faces[:, 0], faces[:, 1]))
    order = np.argsort(owners, kind="stable")
    owners = owners[order]
    link_first = link_first[order]
    link_second = link_second[order]
    changes = np.flatnonzero(owners[1:] != owners[:-1]) + 1
    starts = np.concatenate((np.asarray([0], dtype=np.int64), changes))
    ends = np.concatenate((changes, np.asarray([len(owners)], dtype=np.int64)))
    nonmanifold = 0
    for start, end in zip(starts.tolist(), ends.tolist()):
        if _link_component_count(link_first[start:end], link_second[start:end]) != 1:
            nonmanifold += 1
    return nonmanifold


def triangle_areas(positions, faces):
    import numpy as np

    triangles = positions[faces]
    cross = np.cross(
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    areas = 0.5 * np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(areas)) or np.any(areas <= 1e-12):
        raise ValueError("surface topology repair encountered invalid triangle area")
    return areas


def repair_local_topology(positions, reference_normals, faces, reference_metrics):
    import numpy as np

    empty_report = {
        "applied": False,
        "anomaly_edge_count": 0,
        "candidate_face_count": 0,
        "removed_face_count": 0,
        "removed_face_fraction": 0.0,
        "removed_area_mm2": 0.0,
        "removed_area_fraction": 0.0,
        "initial_displacement_mm": 0.0,
        "post_repair_compact_count": 0,
    }
    if (
        reference_metrics["boundary_edge_count"] == 0
        and reference_metrics["nonmanifold_edge_count"] == 0
        and reference_metrics["nonmanifold_vertex_count"] == 0
    ):
        return positions, reference_normals, faces, reference_metrics, empty_report

    unique_edges, counts, face_edge_ids = edge_incidence(faces)
    anomaly_ids = np.flatnonzero(counts != 2)
    if len(anomaly_ids) == 0:
        raise ValueError(
            "accurate reference surface contains unsupported vertex-fan non-manifold topology"
        )
    if len(anomaly_ids) > LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES * 3:
        raise ValueError("accurate reference topology anomaly is too broad for bounded local repair")

    candidate_mask = np.any(np.isin(face_edge_ids, anomaly_ids), axis=1)
    candidate_faces = np.flatnonzero(candidate_mask)
    if (
        len(candidate_faces) == 0
        or len(candidate_faces) > LOCAL_TOPOLOGY_REPAIR_MAX_CANDIDATE_FACES
    ):
        raise ValueError("accurate reference topology anomaly exceeds local repair candidate budget")

    areas = triangle_areas(positions, faces)
    total_area_mm2 = float(areas.sum(dtype=np.float64))
    if not np.isfinite(total_area_mm2) or total_area_mm2 <= 1e-12:
        raise ValueError("accurate reference surface area is invalid")

    solution = None
    solution_report = None
    max_remove = min(LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACES, len(candidate_faces))
    anomaly_id_set = set(int(value) for value in anomaly_ids.tolist())
    for removal_count in range(1, max_remove + 1):
        removed_face_fraction = removal_count / len(faces)
        if removed_face_fraction > LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_FACE_FRACTION + 1e-15:
            break
        for subset in combinations(candidate_faces.tolist(), removal_count):
            removed_area_mm2 = float(areas[list(subset)].sum(dtype=np.float64))
            removed_area_fraction = removed_area_mm2 / total_area_mm2
            if removed_area_fraction > LOCAL_TOPOLOGY_REPAIR_MAX_REMOVED_AREA_FRACTION + 1e-15:
                continue

            decrements: dict[int, int] = {}
            for face_index in subset:
                for edge_id in face_edge_ids[face_index].tolist():
                    edge_id = int(edge_id)
                    decrements[edge_id] = decrements.get(edge_id, 0) + 1

            valid = True
            for edge_id, decrement in decrements.items():
                remaining = int(counts[edge_id]) - decrement
                if remaining not in (0, 2):
                    valid = False
                    break
            if not valid:
                continue
            for edge_id in anomaly_id_set:
                remaining = int(counts[edge_id]) - decrements.get(edge_id, 0)
                if remaining not in (0, 2):
                    valid = False
                    break
            if not valid:
                continue

            keep = np.ones(len(faces), dtype=bool)
            keep[list(subset)] = False
            (
                repaired_positions,
                repaired_normals,
                repaired_faces,
                post_repairs,
                _,
                _,
            ) = compact_mesh(positions, reference_normals, faces[keep])
            repaired_metrics = topology_metrics(len(repaired_positions), repaired_faces)
            if (
                repaired_metrics["boundary_edge_count"] != 0
                or repaired_metrics["nonmanifold_edge_count"] != 0
                or repaired_metrics["nonmanifold_vertex_count"] != 0
                or repaired_metrics["connected_component_count"]
                != reference_metrics["connected_component_count"]
            ):
                continue

            solution = (repaired_positions, repaired_normals, repaired_faces, repaired_metrics)
            solution_report = {
                "applied": True,
                "anomaly_edge_count": int(len(anomaly_ids)),
                "candidate_face_count": int(len(candidate_faces)),
                "removed_face_count": int(removal_count),
                "removed_face_fraction": float(removed_face_fraction),
                "removed_area_mm2": removed_area_mm2,
                "removed_area_fraction": float(removed_area_fraction),
                "initial_displacement_mm": 0.0,
                "post_repair_compact_count": int(post_repairs),
            }
            break
        if solution is not None:
            break

    if solution is None or solution_report is None:
        raise ValueError(
            "accurate reference topology cannot be repaired within bounded local face-only policy"
        )
    return (*solution, solution_report)


def connected_component_count(vertex_count: int, edges) -> int:
    parent = list(range(vertex_count))
    rank = [0] * vertex_count

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for a, b in edges.tolist():
        union(int(a), int(b))
    return len({find(index) for index in range(vertex_count)})


def topology_metrics(vertex_count: int, faces) -> dict[str, object]:
    import numpy as np

    edges, counts = unique_edges_with_counts(faces)
    boundary_edges = int(np.count_nonzero(counts == 1))
    nonmanifold_edges = int(np.count_nonzero(counts > 2))

    parent = list(range(vertex_count))
    rank = [0] * vertex_count

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for a, b in edges.tolist():
        union(int(a), int(b))

    roots = np.asarray([find(index) for index in range(vertex_count)], dtype=np.int64)
    unique_roots = np.unique(roots)
    component_eulers: list[int] = []
    for root in unique_roots.tolist():
        vertices_mask = roots == root
        component_vertices = int(np.count_nonzero(vertices_mask))
        edge_mask = vertices_mask[edges[:, 0]]
        component_edges = int(np.count_nonzero(edge_mask))
        face_mask = vertices_mask[faces[:, 0]]
        component_faces = int(np.count_nonzero(face_mask))
        component_eulers.append(component_vertices - component_edges + component_faces)

    euler = int(vertex_count - len(edges) + len(faces))
    return {
        "boundary_edge_count": boundary_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
        "nonmanifold_vertex_count": nonmanifold_vertex_fan_count(vertex_count, faces),
        "connected_component_count": len(unique_roots),
        "euler_characteristic": euler,
        "component_euler_signature": sorted(component_eulers),
    }


def adjacency_edges(faces):
    import numpy as np

    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.sort(edges, axis=1)
    return np.unique(edges, axis=0)


def clamp_displacement(candidate, reference, limit_mm: float):
    import numpy as np

    delta = candidate - reference
    distance = np.linalg.norm(delta, axis=1)
    over = distance > limit_mm
    if np.any(over):
        delta[over] *= (limit_mm / distance[over])[:, None]
    return reference + delta


def laplacian_step(positions, edges, factor: float):
    import numpy as np

    sums = np.zeros_like(positions, dtype=np.float64)
    counts = np.zeros(len(positions), dtype=np.int64)
    np.add.at(sums, edges[:, 0], positions[edges[:, 1]])
    np.add.at(sums, edges[:, 1], positions[edges[:, 0]])
    np.add.at(counts, edges[:, 0], 1)
    np.add.at(counts, edges[:, 1], 1)
    candidate = positions.copy()
    active = counts > 0
    means = sums[active] / counts[active, None]
    candidate[active] += factor * (means - positions[active])
    return candidate


def clamp_volume_cell_bounds(positions, affine, shape):
    import numpy as np

    linear = affine[:3, :3]
    translation = affine[:3, 3]
    inverse_linear = np.linalg.inv(linear)
    index_positions = (positions - translation) @ inverse_linear.T
    lower = np.full(3, -0.5, dtype=np.float64)
    upper = np.asarray(shape, dtype=np.float64) - 0.5
    index_positions = np.minimum(np.maximum(index_positions, lower), upper)
    return index_positions @ linear.T + translation


def smooth_bounded(reference_positions, faces, *, limit_mm: float, affine, shape):
    positions = reference_positions.copy()
    edges = adjacency_edges(faces)
    for _ in range(SMOOTHING_ITERATIONS):
        positions = laplacian_step(positions, edges, TAUBIN_LAMBDA)
        positions = clamp_displacement(positions, reference_positions, limit_mm)
        positions = clamp_volume_cell_bounds(positions, affine, shape)
        positions = laplacian_step(positions, edges, TAUBIN_MU)
        positions = clamp_displacement(positions, reference_positions, limit_mm)
        positions = clamp_volume_cell_bounds(positions, affine, shape)
    return positions


def aggregate_normals(reference_normals, inverse, cluster_count: int):
    import numpy as np

    aggregated = np.zeros((cluster_count, 3), dtype=np.float64)
    np.add.at(aggregated, inverse, reference_normals)
    lengths = np.linalg.norm(aggregated, axis=1)
    if np.any(lengths <= 1e-12) or not np.all(np.isfinite(lengths)):
        raise ValueError("cluster orientation reference is invalid")
    return aggregated / lengths[:, None]


def cluster_candidate(smoothed_positions, reference_positions, reference_normals, faces, affine, cell_size: float):
    import numpy as np

    linear = affine[:3, :3]
    translation = affine[:3, 3]
    inverse_linear = np.linalg.inv(linear)
    index_positions = (smoothed_positions - translation) @ inverse_linear.T
    origin = index_positions.min(axis=0) - 1e-9
    keys = np.floor((index_positions - origin) / cell_size).astype(np.int64)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    cluster_count = int(inverse.max()) + 1
    sums = np.zeros((cluster_count, 3), dtype=np.float64)
    counts = np.zeros(cluster_count, dtype=np.int64)
    np.add.at(sums, inverse, smoothed_positions)
    np.add.at(counts, inverse, 1)
    clustered_positions_all = sums / counts[:, None]
    clustered_reference_normals_all = aggregate_normals(
        reference_normals, inverse, cluster_count
    )
    mapped_displacement = np.linalg.norm(
        clustered_positions_all[inverse] - reference_positions, axis=1
    )
    max_displacement_mm = float(mapped_displacement.max(initial=0.0))
    mean_displacement_mm = float(mapped_displacement.mean())
    clustered_faces = inverse[faces]
    (
        clustered_positions,
        clustered_reference_normals,
        clustered_faces,
        repairs,
        cluster_to_output,
        removed_unreferenced,
    ) = compact_mesh(
        clustered_positions_all, clustered_reference_normals_all, clustered_faces
    )
    if removed_unreferenced != 0:
        raise ValueError("vertex clustering produced unsupported unreferenced clusters")
    if np.any(cluster_to_output[inverse] < 0):
        raise ValueError("vertex clustering output mapping is invalid")
    return (
        clustered_positions,
        clustered_reference_normals,
        clustered_faces,
        repairs,
        max_displacement_mm,
        mean_displacement_mm,
    )


def canonical_vertex_normals(positions, faces, orientation_reference):
    import numpy as np

    triangles = positions[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(cross)) or np.any(lengths <= 1e-12):
        raise ValueError("refined surface contains degenerate triangles")
    reference = orientation_reference[faces].mean(axis=1)
    agreement = np.einsum("ij,ij->i", cross, reference)
    magnitude = float(np.sum(np.abs(agreement), dtype=np.float64))
    score = float(np.sum(agreement, dtype=np.float64))
    if (
        not np.all(np.isfinite(agreement))
        or not np.isfinite(magnitude)
        or not np.isfinite(score)
        or magnitude <= 1e-12
        or abs(score) <= max(1e-12, magnitude * 1e-6)
    ):
        raise ValueError("refined surface outward orientation reference is ambiguous")
    if score < 0.0:
        faces = faces[:, [0, 2, 1]]
        cross = -cross
    normals = np.zeros_like(positions, dtype=np.float64)
    np.add.at(normals, faces[:, 0], cross)
    np.add.at(normals, faces[:, 1], cross)
    np.add.at(normals, faces[:, 2], cross)
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths <= 1e-12) or not np.all(np.isfinite(lengths)):
        raise ValueError("refined surface normals are invalid")
    normals /= lengths[:, None]
    return faces, normals


def refine_surface(*, reference_surface: Path, request: dict[str, object], output: Path) -> dict[str, object]:
    import numpy as np

    runtime = runtime_identity()
    if runtime["runtime_fingerprint_sha256"] != request["expected_runtime_fingerprint_sha256"]:
        raise ValueError("surface runtime changed after qualification")
    if sha256_file(reference_surface) != request["reference_surface_sha256"]:
        raise ValueError("accurate reference surface changed")
    payload = reference_surface.read_bytes()
    positions, reference_normals, faces = decode_surface(
        payload, label_id=int(request["label_id"])
    )
    raw_reference_vertex_count = len(positions)
    raw_reference_triangle_count = len(faces)
    if (
        raw_reference_vertex_count > int(request["max_vertices"])
        or raw_reference_triangle_count > int(request["max_triangles"])
    ):
        raise ValueError("reference surface exceeds refinement geometry budget")

    (
        positions,
        reference_normals,
        faces,
        safe_compact_repair_count,
        _,
        _,
    ) = compact_mesh(positions, reference_normals, faces)
    post_compact_vertex_count = len(positions)
    post_compact_triangle_count = len(faces)
    post_compact_metrics = topology_metrics(len(positions), faces)
    post_compact_surface_area_mm2 = float(
        triangle_areas(positions, faces).sum(dtype=np.float64)
    )

    (
        positions,
        reference_normals,
        faces,
        repaired_metrics,
        local_repair,
    ) = repair_local_topology(
        positions,
        reference_normals,
        faces,
        post_compact_metrics,
    )
    if (
        repaired_metrics["boundary_edge_count"] != 0
        or repaired_metrics["nonmanifold_edge_count"] != 0
        or repaired_metrics["nonmanifold_vertex_count"] != 0
        or repaired_metrics["connected_component_count"]
        != post_compact_metrics["connected_component_count"]
    ):
        raise ValueError("surface topology repair did not produce a closed manifold baseline")

    repaired_reference_vertex_count = len(positions)
    repaired_reference_triangle_count = len(faces)
    topology_repair_count = (
        int(safe_compact_repair_count)
        + int(local_repair["removed_face_count"])
        + int(local_repair["post_repair_compact_count"])
    )

    affine = np.asarray(request["array_index_to_patient_lps"], dtype=np.float64)
    if (
        affine.shape != (4, 4)
        or not np.all(np.isfinite(affine))
        or abs(float(np.linalg.det(affine[:3, :3]))) <= 1e-12
    ):
        raise ValueError("Patient LPS affine is invalid")
    singular_values = np.linalg.svd(affine[:3, :3], compute_uv=False)
    minimum_step_mm = float(np.min(singular_values))
    if not np.isfinite(minimum_step_mm) or minimum_step_mm <= 1e-9:
        raise ValueError("Patient LPS affine spacing is invalid")
    smoothing_limit_mm = minimum_step_mm * SMOOTHING_DISPLACEMENT_FRACTION
    total_limit_mm = minimum_step_mm * TOTAL_DISPLACEMENT_FRACTION

    reference_positions = positions.copy()
    volume_shape = tuple(int(item) for item in request["shape"])
    smoothed = smooth_bounded(
        reference_positions,
        faces,
        limit_mm=smoothing_limit_mm,
        affine=affine,
        shape=volume_shape,
    )
    smoothing_displacement = np.linalg.norm(smoothed - reference_positions, axis=1)
    max_smoothing_displacement_mm = float(
        smoothing_displacement.max(initial=0.0)
    )

    best_positions = smoothed
    best_reference_normals = reference_normals
    best_faces = faces
    best_cell_size = 0.0
    best_decimation_cleanup_count = 0
    decimation_applied = False
    best_max_displacement_mm = float(smoothing_displacement.max(initial=0.0))
    best_mean_displacement_mm = float(smoothing_displacement.mean())

    for cell_size in CLUSTER_CELL_SIZES_INDEX:
        try:
            (
                candidate_positions,
                candidate_refs,
                candidate_faces,
                candidate_repairs,
                candidate_max_displacement,
                candidate_mean_displacement,
            ) = cluster_candidate(
                smoothed,
                reference_positions,
                reference_normals,
                faces,
                affine,
                cell_size,
            )
        except ValueError:
            continue
        retention = len(candidate_faces) / raw_reference_triangle_count
        if (
            retention < MIN_TRIANGLE_RETENTION_RATIO
            or len(candidate_faces) >= len(best_faces)
        ):
            continue
        metrics = topology_metrics(len(candidate_positions), candidate_faces)
        if metrics != repaired_metrics:
            continue
        if candidate_max_displacement > total_limit_mm + 1e-9:
            continue
        best_positions = candidate_positions
        best_reference_normals = candidate_refs
        best_faces = candidate_faces
        best_cell_size = cell_size
        best_decimation_cleanup_count = int(candidate_repairs)
        best_max_displacement_mm = candidate_max_displacement
        best_mean_displacement_mm = candidate_mean_displacement
        decimation_applied = True

    bounded_positions = clamp_volume_cell_bounds(best_positions, affine, volume_shape)
    if not np.allclose(bounded_positions, best_positions, rtol=0.0, atol=1e-8):
        raise ValueError("refined surface escaped canonical voxel-cell bounds")
    best_faces, normals = canonical_vertex_normals(
        best_positions, best_faces, best_reference_normals
    )
    final_metrics = topology_metrics(len(best_positions), best_faces)
    if final_metrics != repaired_metrics:
        raise ValueError("refined surface topology changed from repaired baseline")
    max_displacement_mm = best_max_displacement_mm
    mean_displacement_mm = best_mean_displacement_mm
    if max_displacement_mm > total_limit_mm + 1e-9:
        raise ValueError("refined surface exceeds displacement bound")

    positions32 = np.ascontiguousarray(best_positions, dtype="<f4")
    normals32 = np.ascontiguousarray(normals, dtype="<f4")
    indices32 = np.ascontiguousarray(best_faces.reshape(-1), dtype="<u4")
    bounds = tuple(
        float(item)
        for item in np.concatenate(
            (positions32.min(axis=0), positions32.max(axis=0))
        )
    )
    position_bytes = positions32.tobytes(order="C")
    normal_bytes = normals32.tobytes(order="C")
    index_bytes = indices32.tobytes(order="C")
    header = HEADER.pack(
        MAGIC,
        SCHEMA_VERSION,
        int(request["label_id"]),
        len(positions32),
        len(indices32),
        len(position_bytes),
        len(normal_bytes),
        len(index_bytes),
        FLAGS,
    )
    refined_payload = header + position_bytes + normal_bytes + index_bytes
    if len(refined_payload) > int(request["max_payload_bytes"]):
        raise ValueError("refined surface exceeds payload budget")
    with output.open("xb") as handle:
        os.chmod(output, 0o600)
        handle.write(refined_payload)
        handle.flush()
        os.fsync(handle.fileno())

    retention_ratio = len(best_faces) / raw_reference_triangle_count
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": OPERATION,
        "refinement": REFINEMENT,
        "refinement_algorithm_version": REFINEMENT_ALGORITHM_VERSION,
        "label_id": int(request["label_id"]),
        "reference_surface_id": request["reference_surface_id"],
        "reference_surface_sha256": request["reference_surface_sha256"],
        "reference_vertex_count": raw_reference_vertex_count,
        "reference_triangle_count": raw_reference_triangle_count,
        "post_compact_reference_vertex_count": post_compact_vertex_count,
        "post_compact_reference_triangle_count": post_compact_triangle_count,
        "post_compact_reference_surface_area_mm2": post_compact_surface_area_mm2,
        "safe_compact_repair_count": int(safe_compact_repair_count),
        "post_compact_reference_boundary_edge_count": post_compact_metrics["boundary_edge_count"],
        "post_compact_reference_nonmanifold_edge_count": post_compact_metrics["nonmanifold_edge_count"],
        "post_compact_reference_nonmanifold_vertex_count": post_compact_metrics["nonmanifold_vertex_count"],
        "post_compact_reference_connected_component_count": post_compact_metrics["connected_component_count"],
        "post_compact_reference_euler_characteristic": post_compact_metrics["euler_characteristic"],
        "post_compact_reference_component_euler_signature": post_compact_metrics["component_euler_signature"],
        "topology_local_repair_applied": bool(local_repair["applied"]),
        "topology_repair_anomaly_edge_count": int(local_repair["anomaly_edge_count"]),
        "topology_repair_candidate_face_count": int(local_repair["candidate_face_count"]),
        "topology_repair_removed_face_count": int(local_repair["removed_face_count"]),
        "topology_repair_removed_face_fraction": float(local_repair["removed_face_fraction"]),
        "topology_repair_removed_area_mm2": float(local_repair["removed_area_mm2"]),
        "topology_repair_removed_area_fraction": float(local_repair["removed_area_fraction"]),
        "topology_repair_initial_displacement_mm": float(local_repair["initial_displacement_mm"]),
        "topology_repair_post_compact_count": int(local_repair["post_repair_compact_count"]),
        "repaired_reference_vertex_count": repaired_reference_vertex_count,
        "repaired_reference_triangle_count": repaired_reference_triangle_count,
        "repaired_reference_boundary_edge_count": repaired_metrics["boundary_edge_count"],
        "repaired_reference_nonmanifold_edge_count": repaired_metrics["nonmanifold_edge_count"],
        "repaired_reference_nonmanifold_vertex_count": repaired_metrics["nonmanifold_vertex_count"],
        "repaired_reference_connected_component_count": repaired_metrics["connected_component_count"],
        "repaired_reference_euler_characteristic": repaired_metrics["euler_characteristic"],
        "repaired_reference_component_euler_signature": repaired_metrics["component_euler_signature"],
        "vertex_count": len(positions32),
        "triangle_count": len(best_faces),
        "payload_bytes": len(refined_payload),
        "payload_sha256": sha256(refined_payload).hexdigest(),
        "bounds_lps_mm": list(bounds),
        "coordinate_system": "patient_lps",
        "runtime_fingerprint_sha256": runtime["runtime_fingerprint_sha256"],
        "python_version": runtime["python_version"],
        "numpy_version": runtime["numpy_version"],
        "scikit_image_version": runtime["scikit_image_version"],
        "topology_repair_count": topology_repair_count,
        "boundary_edge_count": final_metrics["boundary_edge_count"],
        "nonmanifold_edge_count": final_metrics["nonmanifold_edge_count"],
        "nonmanifold_vertex_count": final_metrics["nonmanifold_vertex_count"],
        "connected_component_count": final_metrics["connected_component_count"],
        "euler_characteristic": final_metrics["euler_characteristic"],
        "component_euler_signature": final_metrics["component_euler_signature"],
        "smoothing_iterations": SMOOTHING_ITERATIONS,
        "max_smoothing_displacement_mm": max_smoothing_displacement_mm,
        "displacement_limit_mm": total_limit_mm,
        "max_displacement_mm": max_displacement_mm,
        "mean_displacement_mm": mean_displacement_mm,
        "decimation_applied": decimation_applied,
        "decimation_cell_size_index": best_cell_size,
        "decimation_cleanup_count": best_decimation_cleanup_count,
        "triangle_retention_ratio": retention_ratio,
        "source_label_map": "immutable",
        "clinical_validation": "not_claimed",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refine one accurate Phase 6A Patient-LPS segmentation surface for Phase 6B"
    )
    parser.add_argument("--reference-surface", required=True)
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--output-surface", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        reference_surface = absolute_regular_file(args.reference_surface, "reference surface")
        request_path = absolute_regular_file(args.request_json, "surface refinement request JSON")
        output = absolute_output(args.output_surface, "surface output")
        report = refine_surface(
            reference_surface=reference_surface,
            request=load_request(request_path),
            output=output,
        )
    except Exception as exc:  # Parent keeps detailed worker diagnostics private.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
