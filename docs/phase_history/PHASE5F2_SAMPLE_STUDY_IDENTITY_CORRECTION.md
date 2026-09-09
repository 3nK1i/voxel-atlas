# Phase 5F2 Correction - Sample Study Identity Preservation

## Problem

The sample catalog previously re-ingested its DICOM payload on every open. Each
ingestion receives a fresh study UUID. Canonical Phase 5C label maps are rightly
bound to one source study UUID, so a reopened sample could be visually identical
but still have no eligible segmentation overlay or 3D surface.

## Correction

Before ingestion, the sample catalog re-verifies the installed payload and builds
an order-independent inventory of each DICOM instance SHA-256 and size. It asks
the DICOM repository for stored studies with the same sample origin and exactly
the same instance inventory.

When candidates exist, the catalog activates one instead of ingesting again.
It prefers a candidate with a canonical label map, then preserves the repository
recency behavior used by the existing latest-study services. New or changed
samples still follow normal ingestion and receive a fresh study identity.

## Safety Boundary

The correction does not loosen Phase 5C binding. It never shows a label map for
a different DICOM instance inventory, study origin, or source-study identity.
It does not copy labels, alter label-map artifacts, or expose raw DICOM metadata
through the public sample API.

## Qualification

Automated checks cover matching inventory reuse, preference for a label-map
owner, new-sample fallback ingestion, repository matching, Phase 4G catalog
regression, Phase 5F2 regression, syntax, Git patient-data safety, and diff
whitespace. Real qualification lists installed samples, reopens the target
sample, and proves that the activated study ID equals the canonical label map's
source study ID.

## Live Switch Restoration Correction

The first identity-preservation delivery exposed a browser lifecycle gap for
reused studies whose canonical volume was already ready. The sample-load route
correctly returned the existing study, but the browser passed it to the volume
builder. That builder intentionally returns immediately for ready volumes, so
the browser never restored the MPR descriptor or initialized the 3D texture.

The corrected client classifies each successful sample activation. A ready
canonical volume follows the same MPR and direct-volume restoration path used at
application startup; an unbuilt but reconstructable study follows construction;
and unqualified geometry remains review-only. This changes presentation
lifecycle only and does not weaken study or label-map binding.
