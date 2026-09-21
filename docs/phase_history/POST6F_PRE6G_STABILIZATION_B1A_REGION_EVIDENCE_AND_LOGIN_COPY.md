# Post-6F / Pre-6G Stabilization B1A — component association and login heading

Authoritative base: `4db68ec9d4218fada2aa538eca2875f664ddd90a` (`phase6-accurate-surfaces`, GitHub `origin`).

## Scope and current limit

This narrow, test-first step makes the read-only Direct-CT diagnostic report a reproducible association between high-HU connected components and broader, lower-threshold support components. It also changes the visible login-page heading to **VoxelAtlas** without changing the form, submit button, authentication, or document title. It does **not** correct the 3D occlusion or the lighting yet and does not qualify Phase 6G.

The affected real-study evidence showed that the first and third most populous 300 HU regions associate uniquely with the second broad-support region, while the second most populous 300 HU region associates uniquely with the first broad-support region. This association is evidence of distinct density regions, **not** a semantic assertion that the first is table or that the second is always patient anatomy. The diagnostic must not infer a universal component-size filtering rule.

## Contract

`associate_isovalue_components` requires an existing float32 3D canonical source, finite thresholds with broad-support threshold strictly lower than the isovalue, and a bounded result size. It labels thresholded regions using 26-connectivity, ranks by voxel count with a deterministic tie-break, and reports which broad-support region encloses each reported high-HU region. Ambiguous assignments are reported without selection. The canonical volume, LPS affine, full extracted surface, source SHA, provenance, and segmentation workflows are unchanged. No patient identifiers or real-study voxels are embedded in tests or this patch.

## Remaining before Stabilization B closure

B1B: Select and qualify a **reversible, display-only** way to suppress confirmed support-associated geometry without hiding uncertain anatomy by default; preserve access to the full 300 HU mesh and resident geometry on mode/profile switches. B2: identify whether residual dark regions are true mesh openings, normals, depth or material/light behavior using controlled Fidelity/Presentation comparison and synthetic geometry. B3: manually confirm login heading, unchanged login, and 1366×768 responsiveness. Only after these steps and full regression/manual qualification may Stabilization B be closed and Phase 6G begin.

No production deployment, storage permission change, source volume processing, or Git remote mutation is part of B1A.
