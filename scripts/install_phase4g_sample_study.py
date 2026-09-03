#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from voxelatlas.sample_catalog import (  # noqa: E402
    SAMPLE_CATALOG_SCHEMA_VERSION,
    SampleStudyCatalogService,
    compute_sample_payload_digest,
)


SAMPLE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install a deidentified public CT/MR study into the VoxelAtlas sample catalog.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("VOXELATLAS_DATA_DIR", "data")),
    )
    parser.add_argument("--dicom-dir", type=Path, required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--modality", required=True, choices=("CT", "MR"))
    parser.add_argument("--body-region", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--license-label", required=True)
    parser.add_argument("--license-url", required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--order", type=int, default=100)
    parser.add_argument("--featured", action="store_true")
    parser.add_argument(
        "--confirm-public-deidentified",
        action="store_true",
        help="Confirm that this study is public, deidentified, and permitted for demonstration use.",
    )
    return parser


def _https_url(value: str, label: str) -> str:
    url = value.strip()
    if not url.startswith("https://") or any(character.isspace() for character in url):
        raise ValueError(f"{label} must be an HTTPS URL")
    return url


def _copy_payload(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError("DICOM source directory must not be a symbolic link")
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("DICOM source directory is unavailable")
    destination.mkdir(parents=True)
    copied = 0
    for candidate in sorted(source.rglob("*")):
        if candidate.is_symlink():
            raise ValueError("DICOM source must not contain symbolic links")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target)
        copied += 1
    if copied == 0:
        raise ValueError("DICOM source directory is empty")


def main() -> int:
    args = _parser().parse_args()
    if not args.confirm_public_deidentified:
        print(
            "INSTALL_SAMPLE=REFUSED\n"
            "REASON=Pass --confirm-public-deidentified only after verifying the source, license, and deidentification.",
            file=sys.stderr,
        )
        return 2

    sample_id = args.sample_id.strip()
    if not SAMPLE_ID.fullmatch(sample_id):
        raise ValueError("sample-id must be a lowercase URL-safe slug")
    if not 0 <= args.order <= 10000:
        raise ValueError("order must be between 0 and 10000")

    catalog_root = args.data_dir.resolve() / "sample_studies"
    final_root = catalog_root / sample_id
    if final_root.exists() or final_root.is_symlink():
        raise ValueError(f"Sample already exists: {sample_id}")
    catalog_root.mkdir(parents=True, exist_ok=True)
    stage = catalog_root / f".install-{sample_id}-{uuid4().hex}"

    try:
        stage.mkdir()
        dicom_root = stage / "dicom"
        _copy_payload(args.dicom_dir, dicom_root)
        digest, file_count, size_bytes = compute_sample_payload_digest(dicom_root)

        if args.preview is not None:
            if args.preview.is_symlink():
                raise ValueError("Preview PNG must not be a symbolic link")
            preview = args.preview.resolve()
            if not preview.is_file():
                raise ValueError("Preview PNG is unavailable")
            if preview.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Preview must be a PNG image")
            shutil.copy2(preview, stage / "preview.png")

        manifest = {
            "schema_version": SAMPLE_CATALOG_SCHEMA_VERSION,
            "sample_id": sample_id,
            "title": args.title.strip(),
            "summary": args.summary.strip(),
            "modality": args.modality,
            "body_region": args.body_region.strip(),
            "source_label": args.source_label.strip(),
            "source_url": _https_url(args.source_url, "source-url"),
            "license_label": args.license_label.strip(),
            "license_url": _https_url(args.license_url, "license-url"),
            "payload_sha256": digest,
            "file_count": file_count,
            "size_bytes": size_bytes,
            "order": args.order,
            "featured": args.featured,
            "installed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (stage / "sample.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        validation = SampleStudyCatalogService(
            data_dir=args.data_dir.resolve(),
            dicom_service=None,  # type: ignore[arg-type]
        )
        stage.replace(final_root)
        if not any(item["sample_id"] == sample_id for item in validation.list_public()):
            raise ValueError("Installed sample did not pass catalog validation")
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        if final_root.exists():
            shutil.rmtree(final_root, ignore_errors=True)
        raise

    print("SAMPLE_STUDY_INSTALLATION=PASS")
    print(f"SAMPLE_ID={sample_id}")
    print(f"MODALITY={args.modality}")
    print(f"FILE_COUNT={file_count}")
    print(f"SIZE_BYTES={size_bytes}")
    print(f"PAYLOAD_SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
