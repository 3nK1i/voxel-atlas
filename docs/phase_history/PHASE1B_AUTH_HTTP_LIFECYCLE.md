# Phase 1B — Authentication HTTP lifecycle

Phase 1B exposes the Phase 1A authentication core through a narrow FastAPI application contract. The visual login page is intentionally deferred until this HTTP lifecycle is green.

## TDD contract

The Phase 1B HTTP tests were added first and initially failed because `voxelatlas.app` did not exist. The implementation then added only the FastAPI/Argon2id/cookie behavior required by that contract.

## Implemented behavior

- Argon2id password hashing/verification adapter using `argon2-cffi`.
- `POST /api/auth/login` with generic invalid-credential responses.
- opaque session identifier delivered only through an `HttpOnly` cookie.
- `SameSite=Lax`, explicit cookie path, TTL-based `Max-Age`, and `Secure` when configured.
- `GET /api/auth/session` for current authentication state.
- `POST /api/auth/logout` with immediate server-side revocation and cookie clearing.
- a minimal protected endpoint used to prove access control behavior.
- the production HTTP application refuses to start until the external username/password-hash pair is configured.
- trusted-host middleware uses the existing allowed-host configuration.

The response body never contains the session token. No frontend/localStorage authentication state is introduced in this step.

## Deliberately deferred

Login rate limiting, CSRF protection for future authenticated state-changing application APIs, persistent/multi-worker session storage, and the visual login page remain explicit follow-on work. They are not implied by this contract.
