# Phase 4G: Curated Sample Study Catalog

Phase 4G adds a polished entry point for opening administrator-installed public demonstration studies. It does not bundle DICOM data, invent dataset identities, or introduce a separate imaging path.

## Locked behavior

- One secondary `Explore Sample Studies` action sits below the primary upload control.
- The gallery lists only strictly validated catalog manifests under the configured private data directory.
- Each card identifies modality, body region, file count, size, source, and license.
- Optional previews are authenticated, same-origin, `no-store`, and never web-static files.
- Replacing an active workspace requires an explicit confirmation.
- A loaded catalog study remains visibly labeled as a sample after refresh.
- Empty installations have a truthful, useful empty state.

## Integrity and provenance

The terminal installer requires source and license HTTPS URLs plus the explicit `--confirm-public-deidentified` operator attestation. It copies without following symbolic links, computes a deterministic SHA256 over relative names, sizes, and content, and publishes through a staging directory. The server re-computes that digest, file count, and byte count before every load.

The confirmation flag records an administrative decision; it is not an automatic deidentification algorithm. Operators must independently verify that the exact study is public, sufficiently deidentified, and permitted for the intended demonstration.

## Imaging path

An accepted sample is passed to `DicomIngestionService.ingest` in deterministic file order. From that point it follows the same canonical-volume, synchronized MPR, authenticated GPU transport, ray marching, medical transfer-function, patient-space clipping, and adaptive-quality path as an uploaded study.

## Repository safety

No `.dcm`, canonical volume, rendering derivative, sample payload, or preview image is part of the Phase 4G delivery. Installed datasets belong under `VOXELATLAS_DATA_DIR/sample_studies`, outside Git and outside `web/`.
