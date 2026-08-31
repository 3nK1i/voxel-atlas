# Phase 1C — Login UI

Phase 1C adds the first production-facing VoxelAtlas page on top of the Phase 1B authentication HTTP lifecycle.

## Scope

- serve `/login` and redirect `/` to the correct authenticated/anonymous destination;
- protect `/workspace` with the existing opaque cookie session;
- serve the preserved browser viewer as the temporary authenticated workspace target;
- reproduce the supplied login visual language with responsive HTML/CSS controls rather than using the screenshot as a page background;
- copy the authoritative product logo into `web/assets/logo.png` for runtime use;
- provide a CSS fallback placeholder if that runtime image is unavailable;
- keep `design/reference/login.png`, `design/reference/logo.png`, and `design/reference/ui.png` unchanged.

## Asset contract

`web/assets/` is the runtime asset folder. `design/reference/` remains the immutable reference source. The application must never depend on reference screenshots as runtime backgrounds.

## Deferred

The final dashboard replaces the preserved viewer workspace in a later phase. Login rate limiting, CSRF for future authenticated state-changing application APIs, persistent multi-worker session storage, and deployment hardening remain separate planned work.

## Visual validation refinement

Desktop manual validation showed the first-pass login card was oversized for practical browser viewports. The final Phase 1C styling uses a compact 480 px desktop card, a viewport-aware 140–176 px logo, 52 px controls, and a short-height desktop profile so the complete form remains centered and visible on common laptop displays without vertical scrolling.
