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
