# Phase 1A — Authentication core

Phase 1A is the first implementation step on `phase1-login-auth`. It establishes the credential/session domain contract before any login HTML, FastAPI route, or cookie handling is added.

## TDD evidence

The new authentication test contract was written first against the accepted Phase 0 checkpoint. The targeted red run failed because `voxelatlas.auth` did not exist. The narrow implementation then introduced the authentication core and configuration fields required by that contract.

## Scope

- optional paired `VOXELATLAS_AUTH_USERNAME` / `VOXELATLAS_AUTH_PASSWORD_HASH` configuration;
- bounded session TTL configuration;
- generic credential failure semantics;
- injected password-verifier boundary for the upcoming Argon2id adapter;
- cryptographically random opaque session identifiers;
- server-side storage of session-token SHA-256 digests rather than raw tokens;
- expiry and immediate logout invalidation;
- process-local session-store implementation as a Phase 1 development contract.

The process-local store is deliberately not presented as the final multi-worker production session backend. That choice remains staged for hardening after the login/auth HTTP lifecycle is working and tested.

## Out of scope

- FastAPI login/logout routes;
- Argon2id adapter wiring;
- cookies and CSRF;
- rate limiting;
- login page HTML/CSS;
- dashboard rendering.

The authoritative `logo.png`, `login.png`, and `ui.png` references remain unchanged and will be consumed by the visual login step rather than modified here.
