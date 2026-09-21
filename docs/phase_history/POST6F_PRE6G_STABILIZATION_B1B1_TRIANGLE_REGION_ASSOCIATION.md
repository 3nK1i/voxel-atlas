# Post-6F / Pre-6G Stabilization B1B1 — triangle-to-region qualification

Base: `bc5f3b9d21a824ab94f77d4df09d078b5f506538` on `phase6-accurate-surfaces` (GitHub).

B1A provided read-only evidence associating 300 HU connected regions with broad
-500 HU support regions. B1B1 implements **synthetic-only qualification** of how
*already extracted* marching-cubes triangles may be conservatively assigned to
one of the two largest distinct broad-support regions, without any diagnosis of
which region is a patient, table or artifact.

`partition_direct_ct_triangles` consumes an immutable float32 index-space CT,
index-space vertices, and the original face index buffer. It returns one byte
per triangle: 0 for unresolved/other regions, 1 and 2 for the two largest broad
support regions by voxel count, with deterministic component-ID tie-breaking.
The result contains every triangle exactly once. If a triangle's vertices
cannot be associated unambiguously with one ranked region, it stays in label 0
and is **never deleted or silently assigned to another region**. This is
presentation metadata only; source voxels, original faces, Patient-LPS affine,
complete 300 HU extraction and provenance remain unchanged.

Important: **No worker, API, browser visibility, rendering, or production behavior
is changed in B1B1.** The live slab will remain visible until later B1B wiring
has passed contract tests and real-study qualification. Future controls must
begin in full-geometry mode, keep a reversible full-view option, retain
unresolved triangles, and require explicit user confirmation of the region to
hide. Never assume broad-support rank 1 or 2 identifies anatomy on every scan.

Run `bash scripts/run_post6f_pre6g_stabilization_b1b1_checks.sh` in the full
local GitHub checkout; the ZIP itself includes no patient data, binaries,
volumes, segmentation artifacts, model weights or production configuration.
No clinical validation is claimed.
