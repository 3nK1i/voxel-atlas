# VoxelAtlas

VoxelAtlas is a web-based medical imaging workspace under active development. V1 is centered on one end-to-end product flow: **DICOM data -> canonical patient volume -> interactive patient-specific 3D voxel visualization**.

VoxelAtlas is currently an engineering/research application. It is not a certified diagnostic or medical-device product.

## Current status

The accepted foundation includes FastAPI authentication with Argon2id password verification, opaque server-side sessions, the responsive VoxelAtlas login UI, a deployed production service, the Phase 2B final V1 workspace shell, the Phase 3A DICOM study-ingestion foundation, the Phase 3A-R2 clinical viewer polish, Phase 3B DICOM geometry/reconstruction-readiness qualification, Phase 3C canonical patient-volume construction, and Phase 3D-R2.1 real synchronized MPR integration with final professional presentation, image-registered crosshairs, and harmonized clinical action/selection states. Phase 4A defines a reusable patient-specific reconstruction boundary. Phase 4B adds the immutable source-to-GPU volume contract and bounded derived RG8 representation. Phase 4C1 verifies and initializes the authenticated 3D texture. Phase 4C2 ray marches that texture directly so Full Volume presents the actual uploaded patient voxels with physical proportions and patient orientation preserved. Phase 4D1 removes the legacy demo-surface runtime and locks Full Volume as the only V1 3D representation.

## Locked V1 workspace

The workspace is intentionally focused on medical imaging and anatomical inspection:

- final VoxelAtlas header with ergonomic light/dark mode
- 3-stage workflow: Data -> Reconstruction -> 3D Visualization
- real CT/MR DICOM folder upload and Study/Series metadata discovery
- geometric slice ordering, orientation/spacing validation, and reconstruction-readiness qualification
- canonical float32 patient-volume construction with explicit DICOM LPS coordinate provenance
- study and reconstruction status panel
- large Three.js anatomy viewer
- real Axial / Coronal / Sagittal patient-space MPR with synchronized crosshair, slice navigation, and window/level
- directional anatomical cut only: Axial, Coronal, Sagittal
- Clinical rendering only
- anatomy opacity with direct 0-100% semantics (100% fully opaque)
- synchronized anatomical orientation gizmo with transparent styling and axis arrows
- reset and auto-rotate actions
- one truthful anatomical layer: **Full Volume**

AR/XR, holographic rendering, segmentation, OBJ/STL/GLB patient-surface generation, and specialized legacy cut behavior are outside the V1 workspace. Atlas-region exploration is post-V1.

The authoritative workspace target is `design/reference/workspace_v1_target.png`. The implementation target is approximately 95-100% visual fidelity while preserving real behavior, accessibility, responsiveness, and truthful feature states.

## Prototype retirement

Both original prototype lines are intentionally retired from the current tree. They remain recoverable from Git history and the verified original handoff archive. Phase 2B also removes the specialized demo-generation utilities and model artifact that existed only for the retired behavior.

## Runtime assets

Runtime web assets live under `web/assets/`. Patient Full Volume is created only from the uploaded CT/MRI voxel data. The browser does not load a static anatomy model or substitute demo anatomy when patient-volume rendering is unavailable. Historical model assets remain inactive and are documented in `web/assets/models/README.md`.

The product logo is served from `web/assets/logo.png`. Authoritative design references are stored under `design/reference/`.

## Development environment

Create/activate the project-local Python environment and install the declared backend/test profiles:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/backend.txt -r requirements/test.txt
```

Phase 3A adds `pydicom` for DICOM parsing. Phase 3C promotes `numpy` into the backend runtime profile because patient volumes are now decoded and persisted as float32 arrays. The remaining heavier reconstruction dependency inventory stays in `requirements/medical-processing.txt` until those later phases make it runtime-critical.

## Validation

Run the current compact regression from the repository root:

```bash
bash scripts/run_phase4d1_checks.sh
```

## Locked V1 roadmap

1. foundation, login, authentication, and deployment
2. final V1 workspace target alignment
3. DICOM upload, study ingestion, geometry qualification, canonical patient volume, and real MPR - complete through Phase 3D
4. direct patient-volume rendering foundation and authenticated GPU transport
5. true GPU ray marching of the actual uploaded CT/MRI voxel volume - complete through Phase 4C2
6. medical transfer functions, clipping, synchronization and adaptive performance
7. production security and V1 qualification

Post-V1 work includes atlas-region interaction, AR/XR, advanced planning workflows, PACS/DICOMweb, and additional anatomical atlases.

## Development policy

Development is performed on phase branches. `main` represents accepted validated states. Each implementation step is kept narrow and is closed only after automated checks, targeted manual validation, diff inspection, commit, and push.

Raw medical datasets, generated outputs, `.env`, and local virtual environments are intentionally excluded from Git.

### Phase 3D-R2 - Final Phase 3 presentation

Real axial, coronal and sagittal views are fitted by patient-space physical extent inside full black diagnostic fields, with synchronized crosshairs, orientation markers, physical position, slice index, and compact W/L controls. The temporary scale bracket is retired. The 3D viewer uses the final segmented six-button clinical toolbar with real rotate/pan modes and target-style active states. CT data remains CT; no MRI appearance is fabricated.

### Phase 3D-R2 final selection-state harmonization

The active anatomical layer now uses the same illuminated blue clinical selected state as Directional Cut and the 3D interaction toolbar. Unavailable patient layers remain disabled and truthful, while `aria-pressed` stays synchronized with the active layer. This is a presentation-only closure correction; the patient-space MPR computation and Phase 3 medical-data pipeline are unchanged.

### Phase 3D-R2.1 - Final crosshair and DICOM CTA polish

MPR crosshairs are registered in pixels to the exact contained patient-image rectangle, so crosshair lines stop at the displayed anatomy bounds instead of drifting through black letterbox margins. Pointer mapping continues to use the displayed canvas rectangle. The Upload/Replace DICOM primary action now uses the same premium blue clinical language as the selected Directional Cut and anatomy controls while remaining an action rather than a persistent selected mode.


### Phase 4A - Anatomical reconstruction foundation

Phase 4A introduces the reconstruction service boundary without generating anatomy yet. Future providers consume only the qualified canonical patient volume and must publish triangle meshes directly in DICOM patient LPS millimetres. CT HU is qualified as the first skull source, while MR is the first V1-qualified brain source. Published anatomy is tied to the exact source-volume descriptor and becomes stale automatically if that source changes. Private mesh paths and provider parameters are not exposed by the reconstruction-status API.

### Phase 4B - Direct patient volume rendering foundation

Phase 4B makes the actual canonical CT/MRI voxels the primary V1 3D source. It preserves the full-resolution `float32` medical volume, produces a bounded two-byte-per-voxel RG8 presentation derivative, retains CT HU and MR modality semantics through an explicit decode mapping, and carries the patient-LPS affine into a full voxel-cell texture transform. The artifact is integrity checked, revision bound, authenticated and served with `no-store`. Browser capability is qualified before preparation, while `Full Volume` remains disabled until the Phase 4C ray marcher is real.

### Phase 4C1 - Verified browser volume texture transport

Phase 4C1 downloads the authenticated RG8 artifact only after source and browser qualification. The browser verifies response media type, revision, SHA256 header, `nosniff`, `no-store`, content length, received byte length and a locally computed SHA256 before creating the Three.js `Data3DTexture`. The texture is explicitly initialized on the GPU and is aborted and disposed when superseded, replaced, logged out or unloaded. `Full Volume` remains disabled until Phase 4C2 supplies the real ray marcher.

### Phase 4C2 - True patient-volume ray marching

Phase 4C2 creates a WebGL2 `sampler3D` ray marcher around the verified texture. Every sample decodes the RG8 low/high bytes back to the medical intensity domain, applies a conservative modality-aware baseline mapping, and composites the real voxels front to back with early termination. The voxel-cell affine is converted from DICOM Patient LPS millimetres into the viewer's Right/Superior/Anterior frame, centered, and uniformly scaled without changing physical proportions. `Full Volume` becomes available only after the shader compiles. Transfer-function presets and synchronized clipping remain Phase 4D and Phase 4E work.

### Phase 4D1 - Volume-only workspace

Phase 4D1 makes `Full Volume` the only V1 anatomical layer and removes the demo skull, static GLB loading, surface-material path, and multi-layer controls from the browser runtime. The 3D viewport now displays only the actual uploaded CT/MRI voxel volume. Before that volume is ready, or if GPU preparation fails, the application remains truthful and keeps synchronized MPR available without substituting a model. The canonical medical volume, authenticated transport, physical patient geometry, and C2 ray marcher are unchanged.
