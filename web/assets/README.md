# Runtime image assets

This folder contains images that are served by the VoxelAtlas web application at runtime.

- `logo.png` is the current runtime product logo. Phase 1C seeds it from the authoritative `design/reference/logo.png` asset.
- Keep design-reference screenshots and source references in `design/reference/`; do not point the application at those files directly.
- If a future runtime image is required, place it in this folder with the exact filename documented by the implementation step.
- The login UI includes a built-in CSS placeholder state if `logo.png` cannot be loaded, so a missing image never becomes a broken browser-image icon.

The existing `assets/models/` directory remains reserved for the preserved 3D demo model assets.
