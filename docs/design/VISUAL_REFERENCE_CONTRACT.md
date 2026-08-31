# Authoritative visual reference contract

The three images in `design/reference/` are the authoritative VoxelAtlas visual inputs supplied for the product direction. They are preserved byte-for-byte and covered by automated SHA256 checks.

- `logo.png` is the **product logo**. Production login/dashboard work must use this supplied asset as the visible VoxelAtlas brand mark rather than replacing it with a generated or substitute logo.
- `login.png` is the authoritative **visual reference** for the Phase 1 login screen: composition, spacing, medical-blue tone, card treatment, and overall visual hierarchy should be followed closely while keeping the implementation responsive and functional.
- `ui.png` is the authoritative **visual reference** for the main dashboard: left sidebar, 3D workspace, Axial/Coronal/Sagittal arrangement, restrained controls, and overall medical-tech rendering language should be followed closely.

The login and dashboard images are design references, not screenshots to be used as page backgrounds. Controls shown in the final implementation must have real behavior or remain omitted/disabled until implemented.

`design/reference/SHA256SUMS` records the expected fingerprints of these exact supplied files.
