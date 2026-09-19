# task-manager-api

Clean Architecture Task Management API built with Python and FastAPI.

## Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL, SQLAlchemy 2.0 (async) + asyncpg, Alembic migrations
- **Package manager**: uv
- **Validation/config**: Pydantic v2 + pydantic-settings (`SecretStr` for all credentials)
- **Auth**: JWT bearer access + refresh tokens (`pyjwt`), `bcrypt` password hashing, RBAC
- **Token revocation**: Redis-backed refresh-token rotation + access-token blacklist
- **Rate limiting**: `slowapi`
- **Testing**: pytest, pytest-asyncio, httpx (`AsyncClient`), aiosqlite for isolated test DB
- **Lint/format**: ruff · **Types**: mypy (strict)
- **Containers**: Docker (multi-stage, non-root) + Docker Compose

## Quickstart (Docker)

```bash
make local-run
```

This generates a `.env` with freshly random secrets (if one doesn't already exist —
`scripts/generate_env.sh` never overwrites one) and brings up the full stack.

Or, to generate the secrets yourself:

```bash
cp .env.example .env
# Generate three DIFFERENT secrets and one JWT key, then edit .env:
openssl rand -base64 24   # -> POSTGRES_SUPERUSER_PASSWORD
openssl rand -base64 24   # -> POSTGRES_MIGRATOR_PASSWORD
openssl rand -base64 24   # -> POSTGRES_PASSWORD
openssl rand -hex 32      # -> JWT_SECRET_KEY
openssl rand -base64 24   # -> REDIS_PASSWORD

docker compose up --build
```

API on `http://localhost:8000`, docs on `http://localhost:8000/docs`. Compose runs four
services: `db` (Postgres 16, provisions least-privilege roles on first boot via
`db/init/001_create_roles.sh`), `redis` (7-alpine, password-protected — backs refresh-token
rotation and access-token revocation), `migrate` (one-shot `alembic upgrade head` using the
DDL-capable migrator role, then exits), and `api` (the long-running server, using only the
DML-only app role). Stop the stack with `make down`.

## Quickstart (local, no Docker)

```bash
uv sync
cp .env.example .env
# For a single local Postgres user without the role split, it's fine to set
# POSTGRES_MIGRATOR_USER/PASSWORD to the same values as POSTGRES_USER/PASSWORD.
# Point at a locally running Postgres (POSTGRES_HOST=localhost in .env — the
# default `db` value only resolves inside the Compose network) — install one
# via your OS package manager, or run just the db container:
#   docker run --rm -p 5432:5432 -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" postgres:16
uv run alembic upgrade head
docker run --rm -p 6379:6379 redis:7-alpine redis-server --requirepass "$REDIS_PASSWORD"
uv run fastapi dev app/main.py
```

A running Redis is required — it backs refresh-token rotation and access-token revocation,
checked on every authenticated request.

## Tests

```bash
uv run pytest
```

Tests run against an in-memory SQLite (aiosqlite) database per test, no Postgres required.

## API flow

1. `GET /v1/health` — liveness check, no auth.
2. `POST /v1/auth/register` — create an account (role always starts as `user`).
3. `POST /v1/auth/login` — exchange credentials for an access token (15 min) + refresh token
   (7 days), returned in the JSON body.
4. `POST /v1/task-lists`, `GET /v1/task-lists`, `GET /v1/task-lists/{id}`,
   `PATCH /v1/task-lists/{id}` — create/list/get/update task lists (`CurrentUser`).
   `DELETE /v1/task-lists/{id}` requires the `admin` role.
5. `GET /v1/task-lists/{id}/tasks` — list a task list's tasks, filterable by `status`/`priority`,
   with a `completion_percentage` computed over the unfiltered set (`CurrentUser`).
6. `POST /v1/task-lists/{id}/invitations`, `GET /v1/task-lists/{id}/invitations` — send/list fake
   collaboration invitations for a task list (logged and persisted, no real email sent;
   `CurrentUser`).
7. `POST /v1/tasks`, `GET /v1/tasks`, `GET /v1/tasks/{id}`, `PATCH /v1/tasks/{id}`,
   `PATCH /v1/tasks/{id}/status`, `PATCH /v1/tasks/{id}/assignee` — create/list/get/update a task,
   change its status, and (re)assign or unassign it (`assignee_id: null`) (`CurrentUser`).
   `DELETE /v1/tasks/{id}` requires the `admin` role (there's no self-service promotion endpoint
   by design — promote via a direct DB write or a future internal admin tool).
8. `POST /v1/auth/refresh` with `{"refresh_token": "..."}` — exchanges it for a new pair and
   rotates the refresh token; the presented one is invalidated immediately, so reusing it (replay)
   is rejected.
9. `POST /v1/auth/logout` (authenticated) with an optional `{"refresh_token": "..."}` — revokes
   the current access token immediately (checked on every subsequent request) and, if provided,
   the refresh token.

## Architecture

Clean Architecture with strict dependency direction: `api -> services -> schemas`/`repositories`
-> `models`. Business logic never imports FastAPI types (`Request`, `Response`, `Depends`).

```
app/
  api/            # FastAPI routers, versioned under v1/, HTTP concerns only
    v1/           # one router module per resource + router.py aggregator
    dependencies.py  # shared FastAPI Depends() wiring (DB session, services)
  schemas/        # Pydantic v2 models (request/response DTOs, validation)
  services/       # Business logic, framework-agnostic; exceptions.py for domain errors
  repositories/   # Data-access layer, one class per aggregate, wraps AsyncSession queries
  models/         # SQLAlchemy 2.0 async ORM models
  core/           # config.py (pydantic-settings), database.py (lazy engine/session/Base),
                   # security.py (bcrypt + JWT), rate_limit.py (slowapi Limiter),
                   # exceptions.py, logging.py, middleware.py (request-id + security headers)
alembic/          # migrations (async env.py, versions/) — connects with the DDL-capable
                   # migrator role, decoupled from app/core/config.Settings
db/init/          # one-shot SQL/shell scripts that provision least-privilege Postgres roles
                   # on first cluster init (see docker-compose.yml's `db` service)
tests/            # pytest, mirrors app/ structure (api/, services/, repositories/, core/)
```

Full ADR-formatted rationale (context, chosen option, tradeoffs) for these and other decisions
lives in [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md), following the standard in
`.claude/rules/adr-standards.md`.

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
- **JWT auth + RBAC.** `POST /v1/auth/login` issues a bearer access token (`app/core/security.py`,
  HS256, 15 min default expiry) carrying only the subject (+ `jti`/`type`) — never a role, so
  authorization (`require_role` in `app/api/dependencies.py`) always re-reads the current role
  from the database and a demoted/deleted user's still-valid token stops working immediately.
  Every `/v1/tasks*` route requires `CurrentUser`; `DELETE /v1/tasks/{id}` additionally requires
  `AdminUser`.
- **Refresh-token rotation + revocation list (Redis).** Refresh tokens (7-day default) are
  single-use: `POST /v1/auth/refresh` deletes the presented token's Redis allowlist entry and
  issues a new pair, so replaying an already-rotated refresh token is rejected
  (`InvalidRefreshTokenError`, 401). `POST /v1/auth/logout` blacklists the current access token's
  `jti` (checked on every request via `get_current_access_claims`) and revokes the associated
  refresh token if provided. Both key families carry a Redis TTL equal to the token's remaining
  lifetime, so entries self-expire. See ADR-006.
- **No user enumeration.** Login returns the same generic "Invalid email or password" for both an
  unknown email and a wrong password (`InvalidCredentialsError`).
- **Generic error responses.** All domain/auth exceptions map to fixed, non-leaking messages in
  `app/main.py`; a catch-all `Exception` handler guarantees any unhandled error returns a generic
  500 body while the real exception is logged server-side against the request's `X-Request-ID`.
  `debug=False` by default, so FastAPI/Starlette never render interactive tracebacks.
- **Security headers on every response** (`app/core/middleware.py`): `Content-Security-Policy`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`,
  `Permissions-Policy`, `Strict-Transport-Security` (assumes TLS termination in front of this
  app).
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
- Secrets manager integration (Vault/AWS Secrets Manager/Azure Key Vault) for non-local
  environments, replacing `.env` files.
- Metrics/observability (Prometheus `/metrics`, OpenTelemetry traces).
- Pagination metadata (total count, next/prev cursors) on `GET /v1/tasks` — currently offset/limit
  only, no envelope.
- Soft delete / audit trail on `TaskModel` and `UserModel` if the domain needs history instead of
  hard deletes.
