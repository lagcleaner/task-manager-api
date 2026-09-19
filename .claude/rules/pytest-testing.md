---
paths: ["tests/**"]
---

# Pytest testing

Rules for tests under `tests/`.

## File and function naming

- Test files: `test_<module_under_test>.py`, mirroring the `app/` structure it covers (e.g. `app/services/task_service.py` -> `tests/services/test_task_service.py`).
- Test functions: `test_<behavior>_<condition>`, e.g. `test_create_task_raises_when_title_empty`. Avoid vague names like `test_task1`.

## Async and fixtures

- Async tests use `@pytest.mark.asyncio` (or `pytest-asyncio` in `auto` mode if configured in `pyproject.toml` — check before adding the marker manually).
- DB-touching fixtures are function-scoped and wrap each test in a transaction that's rolled back afterward (or use a fresh test DB/schema per test run) — tests must not leak state into one another.
- Shared fixtures (DB session, test client, factory helpers) live in `tests/conftest.py` or a nearby `conftest.py`, not copy-pasted per test file.

## HTTP testing

- Use `httpx.AsyncClient` (with `ASGITransport` pointed at the FastAPI app) for endpoint tests, not `TestClient` from `starlette.testclient`, to stay consistent with the app's async nature.
- Endpoint tests assert on status code AND response body shape (parse into the relevant `*Read` schema or check specific fields), not just "it returned 200".

## Isolation

- Unit tests for `app/services/` mock/stub the DB session or repository, not a real database.
- Integration tests for `app/api/` use a real (test) database via fixtures, not mocks, to catch wiring issues between layers.
- Never depend on test execution order; each test sets up its own data.
