---
paths: ["app/repositories/**"]
---

# Repositories

Rules for the data-access layer under `app/repositories/`.

## Responsibility

- One repository class per aggregate/resource (`TaskRepository`), suffixed `Repository`, taking an `AsyncSession` in its constructor.
- Repositories hold single-table queries only (`get_by_id`, `list_all`, `add`, `delete`) — no cross-table orchestration, no business rules, no commits.
- Repositories never call `session.commit()` — the caller (a service) owns the transaction boundary. Repositories may `flush()` to get generated PKs before returning.
- Repositories return ORM models (`app/models/`), never Pydantic schemas — schema shaping happens in `app/services/` or `app/api/`.

## Framework isolation

- Repositories never import from `fastapi`. They receive a plain `AsyncSession` and plain arguments.
- Query logic (SQLAlchemy `select`/`update`/`delete` statements) lives here, not inline in `app/services/` or `app/api/`, once a repository exists for that resource.

## Naming

- Files: `<resource>_repository.py` (e.g. `task_repository.py`).
- Methods use plain verbs (`get_by_id`, `list_all`, `add`, `delete`) — not HTTP-shaped names (`get`, `post`).
