# Phase 6C — Polished multi-structure anatomical presentation

Expected continuation base: `bd96d98e78b88cae5d525f3332716fa18744aa73` on `phase6-accurate-surfaces`.

## Scope

Phase 6C is a presentation-only continuation of the closed Phase 6A/6B surface pipeline. It does not alter canonical segmentation labels, Patient-LPS geometry, topology repair, smoothing, decimation, provenance, or surface payload generation.

The Phase 6C browser can keep multiple refined segmentation surfaces resident and visible in the same Patient-LPS scene. A newly loaded study still begins conservatively with only the currently selected structure activated for 3D presentation. Selecting additional visible structure rows activates their refined surfaces without removing already active structures. `Show all` explicitly opts into progressive construction of all visible surfaces; `Hide all` and single-structure isolate remain available. Advanced arbitrary multi-selection/group isolation remains Phase 6F.

## Presentation contract

- Phase 6B `refined` remains the requested 3D presentation quality.
- Multiple loaded meshes coexist in one segmentation surface group.
- Browser construction is bounded to two concurrent surface requests so an explicit `Show all` does not fan out unbounded heavy jobs.
- Hidden meshes remain browser-resident within the active study so ordinary show/hide and color/opacity edits do not force regeneration.
- Changing the canonical label-map/study aborts pending requests and disposes resident patient meshes.
- Structure palette colors remain synchronized with the existing Phase 5E presentation model and MPR overlays.
- Surface materials use matte `MeshStandardMaterial` shading with smooth supplied Patient-LPS normals, zero metalness, controlled roughness, and opacity-aware depth writing.
- Key/fill/rim directional lighting complements the existing hemisphere light. No shadows, post-processing, geometry displacement, or synthetic anatomical detail is introduced.
- The selected structure receives only a subtle material/render-order emphasis; its underlying geometry and canonical color remain unchanged.

## Progressive multi-structure behavior

The Phase 5E `visible` state still controls synchronized segmentation overlays. Phase 6C adds a presentation-only `surfaceVisible` state:

- initial load: first selected visible structure is activated in 3D;
- select another visible row: its 3D surface is added while already active surfaces remain;
- structure checkbox on/off: synchronizes that structure's 3D surface activation;
- Show all: explicitly activates all visible 3D surfaces progressively;
- Hide all: hides all overlay and 3D structures;
- Isolate: preserves the existing single-structure isolation semantics;
- Reset: restores overlay visibility/colors/opacities and returns 3D presentation to the selected structure.

This avoids automatically launching dozens of heavy surface refinements simply because the Phase 5E overlay catalog defaults to all present labels visible.


## Surface construction feedback

Manual real-study review exposed an ergonomic gap: refined surface construction can take several seconds for large structures even though the rest of the workspace remains responsive. Phase 6C therefore exposes real browser-known lifecycle state without inventing worker percentages.

- selected structures immediately report `Queued <name> surface…` or `Building <name> surface…` in the 3D surface summary;
- each anatomical structure row exposes a compact idle / queued / building / ready / failed state indicator;
- aggregate progress uses truthful completed counts such as `2/3 ready`; no synthetic percentage is shown;
- the existing two-request concurrency bound remains unchanged; queued work remains distinguishable from active work;
- already resident hidden surfaces report ready and remain reusable within the active study;
- study/label-map changes still abort pending work and clear all patient-specific surface state;
- this is presentation feedback only and does not add an asynchronous backend job protocol, WebSocket/EventSource progress channel, or change Phase 6B surface generation.

## Locked boundaries

Phase 6C does **not** introduce:

- on-demand segmentation execution (Phase 6D0),
- volume-derived intensity/CT-HU surfaces (Phase 6D1),
- Volume / Surface / Combined reconstruction cards (Phase 6D2),
- Fidelity / Presentation profiles (Phase 6E),
- arbitrary multi-isolation, group opacity, exploded views, or advanced structure interaction (Phase 6F),
- surface-to-mask fidelity metrics (Phase 6G),
- export formats (Phase 6H),
- clinical or diagnostic claims.

## Qualification

Automated Phase 6C validation covers progressive multi-residency, bounded concurrent loading, retained Phase 6B response/provenance verification, matte standard materials, smooth shading, presentation lighting, study-clear disposal, Phase 6A/6B regression, source-label immutability, roadmap boundaries, and browser syntax.

Real-study qualification must be run separately on a small set of present labels using the qualified isolated surface runtime, followed by manual browser review of at least three simultaneously rendered structures. The canonical label map must remain byte-identical.
