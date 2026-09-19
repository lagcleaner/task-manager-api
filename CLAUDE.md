# task-manager-api

Clean Architecture Task Management API built with Python and FastAPI.

## Architecture

The project follows Clean Architecture with strict dependency direction: `api` depends on `services`, `services` depend on `schemas` and repository interfaces, `models` are the persistence layer. Business logic never imports FastAPI types (`Request`, `Response`, `Depends`).

```
app/
  api/          # FastAPI routers, versioned under v1/, HTTP concerns only
  schemas/      # Pydantic v2 models (request/response DTOs, validation)
  services/     # Business logic, framework-agnostic
  models/       # SQLAlchemy 2.0 async ORM models
  core/         # config, DB session, security, shared utilities
tests/          # pytest, mirrors app/ structure
```

Directory-specific conventions live in `.claude/rules/*.md` and are loaded automatically based on the file path being edited. Read them before editing files in `app/api/`, `app/schemas/`, `app/models/`, `app/services/`, or `tests/`.

## Commands

- Install deps: `uv sync`
- Run dev server: `uv run fastapi dev app/main.py`
- Run tests: `uv run pytest`
- Run a single test: `uv run pytest tests/path/to/test_file.py::test_name`
- Lint: `uv run ruff check .`
- Lint with autofix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`
- Type check: `uv run mypy app`

Always use `uv run <cmd>` instead of invoking `python`/`pytest`/`ruff` directly, so the project's virtualenv is used.

## Naming conventions

- Files and modules: `snake_case.py`.
- Classes: `PascalCase` (`TaskService`, `TaskCreate`, `TaskModel`).
- Functions and variables: `snake_case`.
- Pydantic schemas suffixed by intent: `TaskCreate`, `TaskUpdate`, `TaskRead` — never a bare `Task` schema shared across create/update/read.
- SQLAlchemy models suffixed `Model` (`TaskModel`) to avoid name collisions with schemas of the same domain concept.
- Test files: `test_<module>.py`, test functions: `test_<behavior>_<condition>`.

## General guidance for the AI

- Prefer editing existing files over creating new ones.
- Keep business logic out of `app/api/`; routers should only validate input, call a service, and shape the HTTP response.
- Never introduce a new dependency without checking `pyproject.toml` first — reuse what's already there.
- Run `uv run ruff check --fix` and `uv run ruff format` on any Python file you touch (this also happens automatically via hooks — see `.claude/settings.json`).
- Run `uv run pytest` for touched areas before declaring a task done.
- Do not commit `.env` files or secrets.
