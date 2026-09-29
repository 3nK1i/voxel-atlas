#!/usr/bin/env python3
"""6H-A local-only source and numerical preflight. Do not publish study identifiers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from voxelatlas.dicom_mpr import CanonicalMprService  # noqa: E402
from voxelatlas.segmentation_label_maps import SegmentationLabelMapService  # noqa: E402
from voxelatlas.segmentation_surface_real_study_qualification import (  # noqa: E402
    QualificationServices, RealStudyQualificationError, qualify_real_study,
)
from voxelatlas.segmentation_surfaces import SegmentationSurfaceService  # noqa: E402
from voxelatlas.volume_rendering import VolumeRenderingService  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description='Local 6H-A fidelity harness; preflight is source-read-only')
    p.add_argument('--data-dir', required=True, type=Path)
    p.add_argument('--label-map-id', required=True)
    p.add_argument('--label-id', required=True, type=int)
    p.add_argument('--expected-study-id', help='Optional exact latest-study guard; never printed')
    p.add_argument('--surface-python', type=Path, help='Qualified 6A worker executable, required with --execute')
    p.add_argument('--execute', action='store_true', help='Run bounded 6G report; 6A/6B worker scratch is temporary')
    p.add_argument('--mesh-samples', type=int, default=128)
    p.add_argument('--contour-samples', type=int, default=96)
    args = p.parse_args()
    if args.execute and (args.surface_python is None or not args.surface_python.expanduser().is_file()):
        p.error('--execute requires an existing --surface-python')
    try:
        data_dir = args.data_dir.expanduser().resolve(strict=True)
        # Preflight is the default; no surface service is constructed in that mode.
        surface_service = None
        if args.execute:
            # Preserve the venv executable symlink; do not resolve it to system Python.
            python_path = os.path.abspath(os.path.expanduser(str(args.surface_python)))
            surface_service = SegmentationSurfaceService(
                data_dir=data_dir, worker_python=python_path,
                worker_script=ROOT / 'scripts/phase6a_surface_worker.py',
                refinement_worker_script=ROOT / 'scripts/phase6b_surface_worker.py',
            )
        services = QualificationServices(
            volume=VolumeRenderingService(data_dir=data_dir),
            labels=SegmentationLabelMapService(data_dir=data_dir),
            mpr=CanonicalMprService(data_dir=data_dir), surfaces=surface_service,
        )
        result = qualify_real_study(
            data_dir=data_dir, label_map_id=args.label_map_id,
            label_id=args.label_id, services=services,
            execute=args.execute, expected_study_id=args.expected_study_id,
            mesh_sample_limit=args.mesh_samples, contour_sample_limit=args.contour_samples,
        )
    except Exception as exc:
        # Do not emit exception text: underlying services can embed identifiers,
        # filenames, paths or other patient-specific metadata in an exception.
        print('PHASE6H_A_STATUS=BLOCKED')
        print('FAILURE_CLASS=' + type(exc).__name__)
        print('LOCAL_DIAGNOSTIC=Review locally; do not paste raw traces or patient identifiers')
        return 2
    print('PHASE6H_A_MODE=' + ('EXECUTE' if args.execute else 'PREFLIGHT'))
    print('PHASE6H_A_STATUS=' + result['status'].upper())
    print('SOURCE_AND_MPR_BOUND=YES')
    print('SOURCE_ARTIFACTS_CHANGED=NO')
    print('ROI_WITHIN_6G_BUDGET=' + ('YES' if result['roi']['roi_within_6g_budget'] else 'NO'))
    print('ACQUISITION_BOUNDARY_CONTACT=' + ('YES' if result['roi']['acquisition_boundary_contact'] else 'NO'))
    if args.execute:
        for quality in ('accurate', 'refined'):
            print(quality.upper() + '_STATUS=' + result['fidelity']['surfaces'][quality]['status'].upper())
        print('WHOLE_SURFACE_HAUSDORFF=NOT_COMPUTED')
    print('CLINICAL_VALIDATION=NOT_CLAIMED')
    print('PHASE6H_A_LOCAL_HARNESS_OK=YES')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
