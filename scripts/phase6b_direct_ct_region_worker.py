#!/usr/bin/env python3
"""Isolated, read-only region evidence for one *existing* VXVS CT surface.

This is display metadata only. It does not extract a mesh, alter a volume,
identify anatomy, or decide which region to hide.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.direct_ct_surface_regions import partition_direct_ct_triangles  # noqa: E402

HEADER = struct.Struct('<4s7I')
MAX_SURFACE_BYTES = 160 * 1024 * 1024


def file_digest(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def evidence(volume_path: Path, payload_path: Path, request: dict, output: Path) -> dict:
    for path in (volume_path, payload_path):
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError('Region evidence input is not a regular absolute file')
    if not output.is_absolute() or output.is_symlink() or output.exists() or not output.parent.is_dir():
        raise ValueError('Region evidence output is unsafe')
    if payload_path.stat().st_size > MAX_SURFACE_BYTES:
        raise ValueError('Region evidence surface budget exceeded')
    for key in ('surface_sha256', 'source_sha256'):
        value = request.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Region evidence source binding is invalid')
    if file_digest(volume_path) != request['source_sha256'] or file_digest(payload_path) != request['surface_sha256']:
        raise ValueError('Region evidence source binding changed')
    volume = np.load(volume_path, mmap_mode='r', allow_pickle=False)
    if volume.ndim != 3 or volume.dtype != np.float32 or any(n < 2 for n in volume.shape):
        raise ValueError('Region evidence volume contract is invalid')
    affine = np.asarray(request.get('array_index_to_patient_lps'), dtype=np.float64)
    if affine.shape != (4, 4) or not np.all(np.isfinite(affine)) or not np.allclose(affine[3], [0,0,0,1], rtol=0, atol=0):
        raise ValueError('Region evidence affine contract is invalid')
    if abs(float(np.linalg.det(affine[:3, :3]))) <= 1e-12:
        raise ValueError('Region evidence affine is singular')
    isovalue = float(request.get('isovalue'))
    body_threshold = -500.0
    if not np.isfinite(isovalue) or isovalue <= body_threshold:
        raise ValueError('Region evidence threshold is not qualified')
    payload = payload_path.read_bytes()
    if len(payload) < HEADER.size:
        raise ValueError('Region evidence surface is truncated')
    magic, version, vertex_count, index_count, position_bytes, normal_bytes, index_bytes, flags = HEADER.unpack_from(payload)
    if (magic != b'VXVS' or version != 1 or flags != 1 or vertex_count <= 0
        or index_count <= 0 or index_count % 3 or position_bytes != vertex_count * 12
        or normal_bytes != vertex_count * 12 or index_bytes != index_count * 4
        or len(payload) != HEADER.size + position_bytes + normal_bytes + index_bytes
        or index_count // 3 != request.get('triangle_count')):
        raise ValueError('Region evidence surface contract is invalid')
    pos_start = HEADER.size
    positions = np.frombuffer(payload, dtype='<f4', count=vertex_count * 3, offset=pos_start).reshape(-1, 3).astype(np.float64)
    idx_start = HEADER.size + position_bytes + normal_bytes
    faces = np.frombuffer(payload, dtype='<u4', count=index_count, offset=idx_start).reshape(-1, 3)
    inverse = np.linalg.inv(affine)
    vertex_index = (positions - affine[:3, 3]) @ inverse[:3, :3].T
    # Float32 Patient LPS transport can move a point by a small fraction of a voxel.
    # Only tolerate encoding roundoff, not genuinely out-of-volume positions.
    lower = np.min(vertex_index, axis=0)
    upper = np.max(vertex_index - (np.asarray(volume.shape) - 1), axis=0)
    if np.any(lower < -0.001) or np.any(upper > 0.001):
        raise ValueError('Region evidence vertex lies outside canonical volume')
    vertex_index = np.clip(vertex_index, 0, np.asarray(volume.shape) - 1)
    partition = partition_direct_ct_triangles(
        volume=volume, vertices=vertex_index, faces=faces,
        isovalue=isovalue, body_threshold=body_threshold,
    )
    labels = partition.triangle_regions.tobytes(order='C')
    if len(labels) != request['triangle_count'] or sum(partition.face_counts) != request['triangle_count']:
        raise ValueError('Region evidence face partition is incomplete')
    if file_digest(volume_path) != request['source_sha256'] or file_digest(payload_path) != request['surface_sha256']:
        raise ValueError('Region evidence sources changed during qualification')
    with output.open('xb') as handle:
        os.chmod(output, 0o600)
        handle.write(labels)
    return {
        'schema_version': 1,
        'triangle_count': len(labels),
        'labels_sha256': sha256(labels).hexdigest(),
        'face_counts': list(partition.face_counts),
        'body_region_count': partition.body_region_count,
        'classification': 'not_anatomical',
        'full_geometry_retained': True,
        'source_volume_immutable': True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--volume-npy', required=True)
    parser.add_argument('--surface-payload', required=True)
    parser.add_argument('--request-json', required=True)
    parser.add_argument('--output-regions', required=True)
    args = parser.parse_args()
    try:
        report = evidence(Path(args.volume_npy), Path(args.surface_payload),
                          json.loads(Path(args.request_json).read_text(encoding='utf-8')),
                          Path(args.output_regions))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
