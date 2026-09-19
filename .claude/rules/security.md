---
paths: ["app/**", "tests/**", "docker-compose.yml", "Dockerfile", ".env.example", "db/**"]
---

# Security (Zero-Leak Policy)

Cross-cutting rules enforced across the whole codebase, on top of the layer-specific rules.

## Secrets

- No credential, API key, JWT secret, or password — real, placeholder-that-actually-works, or
  test — is ever hardcoded in application code, Docker files, compose files, fixtures, or docs.
  `.env.example` values are non-functional placeholders (`REPLACE_WITH_...`), never a value that
  would actually authenticate anywhere.
- Every secret-typed config field (`app/core/config.py`) is `pydantic.SecretStr`, not `str`. Call
  `.get_secret_value()` only at the point of use (hashing, signing, building a DB URL) — never
  store the unwrapped value in a variable that outlives that call, log it, or put it in an
  exception message.
- `Settings` fields with no safe default (`postgres_password`, `jwt_secret_key`) have **no
  default value** in code — they must come from the environment/secrets manager, so a missing
  `.env` fails startup loudly instead of silently running with a guessable value.
- `app/core/database.py`'s engine/session factory is built lazily (`get_engine()`,
  `get_session_factory()`), not at import time, so importing `Base` for metadata (Alembic) never
  forces `Settings()` — and Alembic connects with its own migrator credentials
  (`POSTGRES_MIGRATOR_*`), never the app's least-privilege runtime role.

## Least privilege

- The database has at least two roles: a DDL-capable `migrator` role used only by the one-shot
  migration step, and a DML-only `app` role used by the running API (see
  `db/init/001_create_roles.sh`). The API process is never handed migrator or superuser
  credentials, not even as unused environment variables it could leak.
- New privileged operations (schema changes, role management) belong in `db/init/` or an Alembic
  migration run by `migrator`, never in application code running as `app`.

## Input validation

- Pydantic schemas whitelist: every accepted field is declared explicitly with a type and, where
  relevant, a constraint (`Field(min_length=..., max_length=...)`) — never a permissive `dict`,
  `**kwargs`, or `Extra.allow` for user input.
- Passwords are validated for minimum length and composition in the schema
  (`app/schemas/user.py`), hashed with `bcrypt` before persistence, and never round-tripped in a
  response body (`UserRead` has no password field).

## AuthN/AuthZ

- Bearer JWTs are the only auth mechanism; access tokens carry only the subject (`sub`), never a
  role — `require_role` (`app/api/dependencies.py`) always re-reads the role from the database, so
  a demoted/deleted user's still-unexpired token stops granting access immediately.
- New endpoints that mutate or read non-public data must depend on `CurrentUser` (any
  authenticated user) or `AdminUser` (RBAC-gated) from `app/api/dependencies.py` — never left
  open by omission.
- Login/registration failure messages never distinguish "unknown email" from "wrong password"
  (`InvalidCredentialsError`), to avoid user enumeration.

## Error handling

- Domain/auth exceptions map to **generic** client-facing messages in `app/main.py`'s exception
  handlers — never `str(exc)` for anything that could carry internal detail, and never a raw
  traceback or exception class name in a response body.
- The catch-all `Exception` handler in `app/main.py` is the last line of defense: it must always
  return a generic 500 body and log the real exception server-side (via `logger.exception`),
  keyed by `request.state.request_id`.

## Transport & headers

- CORS (`app/main.py`) lists explicit origins only (`Settings` rejects `"*"` at startup) and
  keeps `allow_credentials=False` — this API authenticates via `Authorization: Bearer`, never
  cookies, so credentialed CORS is unnecessary attack surface.
- `security_headers_middleware` (`app/core/middleware.py`) sets CSP, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and HSTS on every response.
  TLS termination itself happens in front of this app (reverse proxy/ingress) — HSTS assumes that.
- Rate limiting (`app/core/rate_limit.py`, `slowapi`) applies a default limit to all routes and a
  stricter one to `/v1/auth/*` to slow down credential stuffing/brute force.

## Containers

- `Dockerfile` stays multi-stage; the runtime stage never contains build tools, `uv`, or source
  outside `/app`, and always runs as the non-root `appuser`.
- `docker-compose.yml` services run with `security_opt: [no-new-privileges:true]` and
  `cap_drop: [ALL]`; the `api` service also runs `read_only: true` with a `tmpfs` for `/tmp`.
