---
paths: ["app/api/**"]
---

# API routes

Rules for FastAPI routers under `app/api/`.

## Versioning and structure

- All routes live under a version prefix: `app/api/v1/<resource>.py`, mounted with `prefix="/v1"`.
- One `APIRouter` per resource (e.g. `tasks.py`, `users.py`), included in `app/api/v1/__init__.py` (or `router.py`), never a single monolithic router file.
- Give every router a `tags=["<resource>"]` for OpenAPI grouping.

## Endpoint conventions

- Path params and query params must be explicitly typed with `Path(...)` / `Query(...)`, including `description`, and constraints (`gt`, `le`, `min_length`, etc.) where they apply — never a bare untyped parameter for anything user-facing.
- Request bodies are always a Pydantic schema from `app/schemas/`, never a raw `dict` or loose `**kwargs`.
- Declare `response_model` on every route (or the return type annotation, if using FastAPI's inference) using the `*Read` schema — never return an ORM model instance directly.
- Routers call into `app/services/`; they must not contain query logic, business rules, or direct DB session manipulation beyond passing the session/dependency through.

## Errors

- Raise `HTTPException` with an explicit `status_code` and a structured `detail` (never a bare string when the error can be programmatically handled — prefer a small error schema/dict with `code` and `message`).
- Map domain exceptions from `app/services/` to HTTP status codes in the router (or in a shared exception handler registered in `app/main.py`) — never let a raw domain exception escape as a 500.
- Document non-2xx responses with `responses={...}` on the route decorator so they show up in OpenAPI docs.

## OpenAPI docs

- Every route needs a `summary` and, when the behavior isn't obvious from the name, a `description`.
- Use `status_code=status.HTTP_201_CREATED` (etc.) from `fastapi.status`, never magic numbers.
