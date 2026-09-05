#!/usr/bin/env python3
"""Read-only, dependency-free gate for local H6 browser evidence. Not clinical validation."""
import argparse
import json
import math
from pathlib import Path

MODES = ('dvr', 'mip', 'minip', 'average', 'slice', 'thick-slab')
SLOTS = ('CT-1', 'MR-1', 'CT-2', 'MR-2')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_report(report, max_p95_ms=100):
    errors = []
    if not isinstance(report, dict):
        return ['Report must be a JSON object']
    if report.get('schema') != 'voxelatlas-phase4h6-v1' or report.get('build') != 'phase4h6':
        errors.append('Wrong H6 evidence schema/build')
    faults = report.get('faults')
    if not isinstance(faults, dict):
        errors.append('Missing runtime fault counters')
    else:
        for key in ('windowErrors', 'unhandledRejections', 'contextLosses'):
            if type(faults.get(key)) is not int or faults[key] != 0:
                errors.append(f'Runtime fault counter {key} must be zero')
    captures = report.get('captures')
    if not isinstance(captures, list) or len(captures) != 4:
        return errors + ['Four captures required: CT-1, MR-1, CT-2, MR-2']
    if any(not isinstance(c, dict) for c in captures):
        return errors + ['Malformed capture']
    if [c.get('slot') for c in captures] != list(SLOTS):
        return errors + ['Capture slots must be CT-1, MR-1, CT-2, MR-2 in order']
    for capture in captures:
        slot = capture['slot']
        runtime = capture.get('runtime')
        modes = capture.get('modes')
        if not isinstance(runtime, dict) or not isinstance(modes, dict):
            errors.append(f'{slot}: missing runtime/mode evidence')
            continue
        if runtime.get('modality') != slot.split('-')[0] or runtime.get('ready') is not True:
            errors.append(f'{slot}: matching ready CT/MR volume required')
        if runtime.get('contextLost') is not False or runtime.get('shaderErrors') != 0:
            errors.append(f'{slot}: context/shader check failed or missing')
        if runtime.get('qualityPolicy') != 'balanced':
            errors.append(f'{slot}: repeat evidence on Balanced quality')
        dims = runtime.get('dimensions')
        if not isinstance(dims, list) or len(dims) != 3 or any(type(d) is not int or d <= 0 for d in dims):
            errors.append(f'{slot}: invalid texture dimensions')
        for key in ('geometries', 'textures', 'programs', 'overlayNodes', 'canvasWidth', 'canvasHeight'):
            if type(runtime.get(key)) is not int or runtime[key] < (0 if key == 'overlayNodes' else 1):
                errors.append(f'{slot}: missing/invalid {key}')
        if finite(runtime.get('overlayNodes')) and runtime['overlayNodes'] > 30:
            errors.append(f'{slot}: overlay node pool grew beyond 30')
        for mode in MODES:
            bucket = modes.get(mode)
            stats = bucket.get('continuousFrameIntervalMs') if isinstance(bucket, dict) else None
            if not isinstance(stats, dict):
                errors.append(f'{slot}/{mode}: missing frame evidence')
                continue
            if type(stats.get('count')) is not int or not 30 <= stats['count'] <= 600:
                errors.append(f'{slot}/{mode}: need 30+ foreground continuous frames')
            p95 = stats.get('p95Ms')
            if not finite(p95) or p95 <= 0 or p95 > max_p95_ms:
                errors.append(f'{slot}/{mode}: p95 exceeds {max_p95_ms:g} ms or is missing')
    for first, second in ((captures[0], captures[2]), (captures[1], captures[3])):
        a, b = first.get('runtime'), second.get('runtime')
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        for key in ('dimensions', 'canvasWidth', 'canvasHeight', 'pixelRatio'):
            if a.get(key) != b.get(key):
                errors.append(f'{second["slot"]}: repeat same study and viewport ({key} differs)')
        for key in ('textures', 'geometries', 'programs', 'overlayNodes'):
            if finite(a.get(key)) and finite(b.get(key)) and b[key] > a[key]:
                errors.append(f'{second["slot"]}: {key} grew after warm-up; investigate before acceptance')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    try:
        if args.report.stat().st_size > 1_000_000:
            raise ValueError('Report exceeds 1 MB')
        report = json.loads(args.report.read_text())
        errors = validate_report(report)
    except (OSError, ValueError, TypeError) as exc:
        print(f'Cannot read qualification report: {exc}')
        return 1
    for error in errors:
        print(f'REVIEW: {error}')
    print('PHASE4H6_RUNTIME_EVIDENCE=' + ('FAIL' if errors else 'PASS'))
    print('MANUAL_VISUAL_ACCEPTANCE=REQUIRED')
    print('CLINICAL_VALIDATION=NOT_CLAIMED')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
