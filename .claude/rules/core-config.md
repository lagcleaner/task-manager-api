---
paths: ["app/core/**"]
---

# Core

Rules for cross-cutting infrastructure under `app/core/`.

## Configuration

- All environment/config values are read through `app/core/config.py`'s `Settings` (`pydantic_settings.BaseSettings`), accessed via the cached `get_settings()` — never `os.environ` directly in application code (the one deliberate exception: `alembic/env.py`, which reads its migrator-role credentials directly to stay decoupled from the app's `Settings`/secrets — see `.claude/rules/security.md`).
- Every setting is typed (`PostgresDsn`, `Literal[...]`, `bool`, etc.), never a bare `str` when a more specific type exists. Secret-valued settings (`postgres_password`, `jwt_secret_key`) are `SecretStr`, with no default — see `.claude/rules/security.md`.

## Database

- The declarative `Base` and the lazy `get_engine()` / `get_session_factory()` accessors live in `app/core/database.py` — not redefined elsewhere. The engine/session factory are built lazily (not at import time) so importing `Base` alone never requires `Settings()`.
- `get_db_session()` is the only way routes/services obtain a session, via FastAPI's `Depends`.
- No sync SQLAlchemy engine/session anywhere in this codebase.

## Auth

- Password hashing (`bcrypt`) and JWT encode/decode live in `app/core/security.py` — never re-implemented inline in a service or router.
- `app/core/rate_limit.py` holds the single `Limiter` instance; import it, don't instantiate a second one.

## Exceptions and middleware

- App-wide exception types that aren't domain-specific (i.e. not owned by a single service) go in `app/core/exceptions.py`.
- HTTP-level exception handlers (mapping domain/app exceptions to responses) register in `app/main.py`, not inside routers.
- Cross-cutting middleware (request ID, logging) lives in `app/core/middleware.py`, registered once in `app/main.py`.
