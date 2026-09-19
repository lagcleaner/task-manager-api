# task-manager-api

Clean Architecture Task Management API built with Python and FastAPI.

## Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL, SQLAlchemy 2.0 (async) + asyncpg, Alembic migrations
- **Package manager**: uv
- **Validation/config**: Pydantic v2 + pydantic-settings (`SecretStr` for all credentials)
- **Auth**: JWT bearer tokens (`pyjwt`), `bcrypt` password hashing, RBAC
- **Rate limiting**: `slowapi`
- **Testing**: pytest, pytest-asyncio, httpx (`AsyncClient`), aiosqlite for isolated test DB
- **Lint/format**: ruff · **Types**: mypy (strict)
- **Containers**: Docker (multi-stage, non-root) + Docker Compose

## Quickstart (Docker)

```bash
cp .env.example .env
# Generate three DIFFERENT secrets and one JWT key, then edit .env:
openssl rand -base64 24   # -> POSTGRES_SUPERUSER_PASSWORD
openssl rand -base64 24   # -> POSTGRES_MIGRATOR_PASSWORD
openssl rand -base64 24   # -> POSTGRES_PASSWORD
openssl rand -hex 32      # -> JWT_SECRET_KEY

docker compose up --build
```

API on `http://localhost:8000`, docs on `http://localhost:8000/docs`. Compose runs three
services: `db` (Postgres 16, provisions least-privilege roles on first boot via
`db/init/001_create_roles.sh`), `migrate` (one-shot `alembic upgrade head` using the DDL-capable
migrator role, then exits), and `api` (the long-running server, using only the DML-only app role).

## Quickstart (local, no Docker)

```bash
uv sync
cp .env.example .env
# For a single local Postgres user without the role split, it's fine to set
# POSTGRES_MIGRATOR_USER/PASSWORD to the same values as POSTGRES_USER/PASSWORD.
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

## Tests

```bash
uv run pytest
```

Tests run against an in-memory SQLite (aiosqlite) database per test, no Postgres required.

## API flow

1. `POST /v1/auth/register` — create an account (role always starts as `user`).
2. `POST /v1/auth/login` — exchange credentials for a bearer access token.
3. Call `/v1/tasks*` with `Authorization: Bearer <token>`. Deleting a task requires the `admin`
   role (there's no self-service promotion endpoint by design — promote via a direct DB write or
   a future internal admin tool).

## Architecture decisions

- **Clean/layered architecture** (`api -> services -> repositories -> models`, `schemas` used at
  the `api`/`services` boundary): keeps HTTP concerns, business rules, and persistence queries
  independently testable and replaceable. See `CLAUDE.md` for the full directory contract and
  `.claude/rules/*.md` for per-layer rules.
- **Repository layer** (`app/repositories/`): isolates SQLAlchemy query construction from business
  logic in `app/services/`, so services stay framework- and query-agnostic and are easy to unit
  test with a mocked repository.
- **Domain exceptions** (`app/services/exceptions.py`): services raise typed errors instead of
  `HTTPException`; `app/main.py` maps them to *generic* HTTP responses via registered exception
  handlers, keeping the service layer free of FastAPI imports and keeping internal detail out of
  client-facing error bodies.
- **pydantic-settings for config**: a single typed `Settings` object (`app/core/config.py`),
  cached via `lru_cache`, is the only way the app reads environment variables. Secret fields are
  `SecretStr` with no default, so a missing `.env` fails startup instead of running insecurely.
- **SQLite-in-memory for tests, Postgres for runtime**: trades perfect DB parity for fast, fully
  isolated, dependency-free unit/integration tests. Given the actual query surface (no
  Postgres-only SQL features used), this is an acceptable tradeoff within the challenge's time
  box.
- **Multi-stage Dockerfile**: `uv sync` runs in a builder stage; the runtime image copies only the
  built virtualenv and app code, and drops to a non-root user.

## 🔒 Security Audit & Compliance

Implemented, mapped to the request:

- **Zero hardcoded secrets.** `.env.example` ships only non-functional `REPLACE_WITH_...`
  placeholders. `postgres_password` and `jwt_secret_key` (`app/core/config.py`) have no default —
  a missing `.env` fails startup instead of running with a guessable value. Every secret field is
  `pydantic.SecretStr`; `.get_secret_value()` is called only at point of use (password hashing,
  DB URL construction, JWT signing), never stored unwrapped or logged.
- **Least-privilege database access.** Three separate Postgres roles instead of one superuser
  everywhere: `postgres` (bootstrap only), `migrator` (DDL, used only by the one-shot `migrate`
  compose service), `app` (DML only — `SELECT/INSERT/UPDATE/DELETE`, no `CREATE`/`ALTER`/`DROP`,
  used by the running API). Provisioned in `db/init/001_create_roles.sh`. The long-running `api`
  container never receives the migrator or superuser passwords, not even as unused env vars.
- **Injection prevention.** All queries go through SQLAlchemy 2.0's typed query builder
  (`app/repositories/`) — no raw/string-interpolated SQL anywhere.
- **Whitelisted, strict input validation.** Every request body is a Pydantic v2 schema declaring
  exact fields and constraints (`app/schemas/`); no `dict`/`**kwargs` input. Passwords require
  ≥12 characters plus a letter and a digit (`app/schemas/user.py`) and are hashed with `bcrypt`
  before storage; `UserRead` has no password field, so it can never be echoed back.
- **JWT auth + RBAC.** `POST /v1/auth/login` issues a bearer token (`app/core/security.py`,
  HS256, 15 min default expiry) carrying only the subject — never a role, so authorization
  (`require_role` in `app/api/dependencies.py`) always re-reads the current role from the
  database and a demoted/deleted user's still-valid token stops working immediately. Every
  `/v1/tasks*` route requires `CurrentUser`; `DELETE /v1/tasks/{id}` additionally requires
  `AdminUser`.
- **No user enumeration.** Login returns the same generic "Invalid email or password" for both an
  unknown email and a wrong password (`InvalidCredentialsError`).
- **Generic error responses.** All domain/auth exceptions map to fixed, non-leaking messages in
  `app/main.py`; a catch-all `Exception` handler guarantees any unhandled error returns a generic
  500 body while the real exception is logged server-side against the request's `X-Request-ID`.
  `debug=False` by default, so FastAPI/Starlette never render interactive tracebacks.
- **Security headers on every response** (`app/core/middleware.py`): `Content-Security-Policy`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, `Strict-Transport-Security` (assumes TLS termination in front of this
  app — see Pendientes).
- **Locked-down CORS.** `Settings` rejects a wildcard `cors_origins` at startup; the app also sets
  `allow_credentials=False` since bearer-token auth carries no cookies, and restricts
  methods/headers to what the API actually uses.
- **Rate limiting** (`slowapi`, `app/core/rate_limit.py`): a default limit on every route, a
  stricter one on `/v1/auth/register` and `/v1/auth/login` to slow down credential
  stuffing/brute force.
- **Non-root, minimal containers.** Multi-stage `Dockerfile`; the runtime stage has no build
  tools or `uv`, runs as `appuser`, and has a `HEALTHCHECK`. Compose services run with
  `security_opt: [no-new-privileges:true]` and `cap_drop: [ALL]`; `api` additionally runs
  `read_only: true` with a `tmpfs` for `/tmp`.
- **CSRF: not applicable.** This API authenticates exclusively via `Authorization: Bearer`
  headers, never cookies/sessions, so there is no ambient credential for a cross-site request to
  ride on — adding CSRF tokens here would protect nothing and was deliberately skipped rather than
  added for the sake of a checklist.

**Practices rejected/corrected while building this:**

- A single Postgres superuser for both migrations and runtime traffic (the original scaffold's
  approach) → replaced with the three-role split above.
- `CORS_ORIGINS=["*"]` with `allow_credentials=True` (the original scaffold's default, and also
  an invalid combination browsers reject) → replaced with an explicit allowlist and
  `allow_credentials=False`.
- Embedding the DB password directly in a single `DATABASE_URL` string → replaced with individual
  `SecretStr`-typed credential fields, so the password never appears in a config repr/log line.

## Futuras mejoras / Pendientes

Out of scope for the 4-6h time box, in rough priority order:

- CI/CD (GitHub Actions): lint, type-check, test on PR; build/push image on merge to `main`;
  container vulnerability scanning (Trivy/Grype) as a required check.
- TLS termination: this app assumes a reverse proxy/ingress (nginx, Traefik, cloud LB) terminates
  TLS 1.3 in front of it; the HSTS header is already set, but there's no in-app TLS.
- OAuth2 + PKCE / delegating to an external IdP (Keycloak, Auth0, Cognito) for anything beyond
  first-party password login — e.g. third-party/public clients, SSO. Building a spec-compliant
  authorization server in-house wasn't justified for this challenge's scope; the JWT
  resource-server + RBAC implemented here is the right-sized baseline and the natural seam to
  swap in an external IdP later (verify tokens from that IdP instead of issuing our own).
- Refresh tokens / token revocation list — access tokens currently just expire (15 min default);
  there's no logout-that-actually-invalidates-a-token yet.
- Secrets manager integration (Vault/AWS Secrets Manager/Azure Key Vault) for non-local
  environments, replacing `.env` files.
- Structured/JSON logging + request tracing correlated with the `X-Request-ID` header already
  emitted by `app/core/middleware.py`; ship logs somewhere that can't be tampered with locally.
- Metrics/observability (Prometheus `/metrics`, OpenTelemetry traces).
- Pagination metadata (total count, next/prev cursors) on `GET /v1/tasks` — currently offset/limit
  only, no envelope.
- Postgres-parity test tier (real Postgres via testcontainers) to complement the SQLite unit tests
  for anything that becomes Postgres-specific.
- Soft delete / audit trail on `TaskModel` and `UserModel` if the domain needs history instead of
  hard deletes.
- Distributed rate-limit storage (Redis) — `slowapi`'s default in-memory storage doesn't share
  state across multiple API replicas.
