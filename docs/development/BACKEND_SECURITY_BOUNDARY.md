# Backend and security boundary

Phase 0C3 establishes the backend package/configuration boundary required before authentication work begins. It does not yet expose login routes or start a production web server.

## Configuration

Runtime configuration is read from environment variables through `backend/voxelatlas/config.py`. Real secrets are never committed to Git. `.env.example` contains variable names and safe development defaults only; the session secret remains blank.

Production configuration requires:

- a non-placeholder `VOXELATLAS_SESSION_SECRET` of at least 32 characters;
- secure cookies enabled;
- explicit host restrictions without wildcard hosts;
- patient/study data stored beneath an ignored data directory or another explicitly configured private path.

Development defaults intentionally bind the host contract to `127.0.0.1` and `localhost`.

## Phase 1 authentication direction

The login phase will build on this boundary with:

- FastAPI for the application/API layer;
- Argon2id password hashing through `argon2-cffi`;
- opaque server-side session identifiers in `HttpOnly` cookies rather than credentials/JWTs in browser `localStorage`;
- `Secure` cookies in production and an explicit `SameSite` policy;
- session invalidation on logout;
- generic login errors and rate limiting;
- CSRF protection for state-changing authenticated requests;
- protected dashboard routes.

The Phase 0C3 dependency inventory is intentionally unpinned until the dedicated Phase 1 backend environment is qualified and tested on the target workstation.
## Phase 1A authentication core

The first authentication implementation keeps credential verification and session lifecycle independent of the HTTP framework. `backend/voxelatlas/auth.py` accepts an injected password verifier so the next HTTP step can wire the qualified Argon2id adapter without coupling the core service to FastAPI.

Browser-visible session identifiers are opaque random values. The current process-local server-side store retains only SHA-256 token digests, supports expiry, and revokes immediately on logout. It is a Phase 1 development contract, not yet the final multi-worker production session persistence layer.

## Phase 1B HTTP authentication boundary

FastAPI now exposes the authentication lifecycle through server-side opaque sessions. Argon2id verifies the externally configured password hash. Successful login sets the session identifier only as an `HttpOnly` cookie with `SameSite=Lax`, explicit path/TTL, and `Secure` when configured; API response bodies do not expose the token. Logout revokes the server-side session before clearing the cookie.

The production HTTP application now refuses to start without the authentication username/hash pair, in addition to the existing production session-secret and secure-cookie requirements. Login rate limiting, CSRF protection for future authenticated state-changing application APIs, and persistent multi-worker session storage remain follow-on hardening work rather than hidden assumptions in this phase.

## Phase 1C browser boundary

The login UI is served by FastAPI at `/login`. Anonymous access to `/workspace` redirects to the login page, while authenticated access serves the preserved browser viewer as a temporary workspace target. Static brand/style/script assets are public; authenticated medical-study data must not be placed in the public static asset tree.
