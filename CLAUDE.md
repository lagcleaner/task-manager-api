# task-manager-api

Clean Architecture Task Management API built with Python and FastAPI.

## Architecture

The project follows Clean Architecture with strict dependency direction: `api` depends on `services`, `services` depend on `schemas` and `repositories`, `repositories` depend on `models`, `models` are the persistence layer. Business logic never imports FastAPI types (`Request`, `Response`, `Depends`).

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

Directory-specific conventions live in `.claude/rules/*.md` and are loaded automatically based on the file path being edited. Read them before editing files in `app/api/`, `app/schemas/`, `app/models/`, `app/services/`, `app/repositories/`, `app/core/`, or `tests/`. `.claude/rules/security.md` applies across all of `app/`, `tests/`, and the Docker/compose files — read it before touching auth, secrets, or error handling.

Auth: JWT bearer tokens (`app/core/security.py`), issued by `POST /v1/auth/login`. `app/api/dependencies.py` exposes `CurrentUser` (any authenticated user) and `AdminUser` (RBAC-gated) for use in route signatures — authorization always re-reads the user's role from the database, never trusts a claim baked into the token.

## Commands

- Install deps: `uv sync`
- Run dev server: `uv run fastapi dev app/main.py`
- Run full stack (API + Postgres): `docker compose up --build`
- Run tests: `uv run pytest`
- Run a single test: `uv run pytest tests/path/to/test_file.py::test_name`
- Lint: `uv run ruff check .`
- Lint with autofix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`
- Type check: `uv run mypy app`
- Create a migration: `uv run alembic revision --autogenerate -m "message"`
- Apply migrations: `uv run alembic upgrade head`
- Install git hooks: `make hooks-install`
- Run all pre-commit hooks manually: `make hooks-run`

Always use `uv run <cmd>` instead of invoking `python`/`pytest`/`ruff` directly, so the project's virtualenv is used.

## Git hooks (pre-commit)

`.pre-commit-config.yaml` runs on every commit: `ruff check --fix`, `ruff format`, `mypy app`,
plus generic checks (YAML/JSON syntax, trailing whitespace, large files, no direct commits to
`main`). `pytest -m "not slow"` runs on `pre-push`, not on commit. Every Python hook runs via
`language: system` + `uv run`, so it uses the project's own venv — no separate hook envs, no
version drift from `uv.lock`.

Ruff replaces flake8/black/isort here (see DEVELOPMENT.md) — don't add those tools; they'd fight
ruff over the same job. Before finishing a task that touches `app/`, `tests/`, or config files,
run `make hooks-run` (or `uv run pre-commit run --files <paths>`) so failures surface before the
user commits, not after.

## Naming conventions

- Files and modules: `snake_case.py`.
- Classes: `PascalCase` (`TaskService`, `TaskCreate`, `TaskModel`).
- Functions and variables: `snake_case`.
- Pydantic schemas suffixed by intent: `TaskCreate`, `TaskUpdate`, `TaskRead` — never a bare `Task` schema shared across create/update/read.
- SQLAlchemy models suffixed `Model` (`TaskModel`) to avoid name collisions with schemas of the same domain concept.
- Repositories suffixed `Repository` (`TaskRepository`), one per aggregate.
- Test files: `test_<module>.py`, test functions: `test_<behavior>_<condition>`.

## General guidance for the AI

- Prefer editing existing files over creating new ones.
- Keep business logic out of `app/api/`; routers should only validate input, call a service, and shape the HTTP response.
- Never introduce a new dependency without checking `pyproject.toml` first — reuse what's already there.
- Run `uv run ruff check --fix` and `uv run ruff format` on any Python file you touch (this also happens automatically via hooks — see `.claude/settings.json`).
- Run `uv run pytest` for touched areas before declaring a task done.
- Do not commit `.env` files or secrets.
