# Phase 4C1 - Verified Volume Texture Transport

Phase 4C1 crosses the authenticated Phase 4B rendering artifact into a managed browser and GPU resource. It does not render, segment or infer anatomy.

## Transport verification

The browser downloads the current derivative from the revision-bound authenticated endpoint with same-origin credentials and an explicit `no-store` request policy. Before accepting it, the client verifies:

- the qualified Phase 4B descriptor contract
- response success and the RG8 medical-volume media type
- the full revision header
- the artifact SHA256 header
- `X-Content-Type-Options: nosniff`
- response `Cache-Control: no-store`
- declared and received byte lengths
- a browser-computed SHA256 of the complete received artifact

No filesystem path is accepted or exposed. A stale, partial, substituted or corrupted response never becomes a texture.

## Three.js texture contract

The verified byte buffer is owned by one `Data3DTexture` using the descriptor dimensions `[column, row, slice]`:

- `RGFormat` with `UnsignedByteType`
- explicit WebGL2 `RG8` internal format
- low byte in R and high byte in G
- nearest filtering until the Phase 4C2 shader defines medically controlled sampling
- clamp-to-edge wrapping, no mipmaps and one-byte unpack alignment
- no color-space conversion

The existing renderer initializes the texture so allocation is exercised before Phase 4C2 depends on it.

## Lifecycle and fallback

Only one patient-volume texture is retained. A replacement study aborts any active transfer, disposes the previous GPU texture and releases the application reference. Logout and page unload also dispose it. Superseded asynchronous work cannot overwrite the newer study state.

Any capability, preparation, transport, integrity or texture failure leaves synchronized MPR available. `Full Volume` remains disabled and no ray-marched image is claimed in this step.

## Out of scope

- volume proxy geometry
- `sampler3D` shader code
- ray entry/exit computation
- compositing or early ray termination
- CT/MR transfer functions
- volume-layer activation
- clipping synchronization
- adaptive resolution
