---
paths: ["app/services/**"]
---

# Business services

Rules for business logic under `app/services/`.

## Framework isolation

- Services never import from `fastapi` (`Request`, `Response`, `Depends`, `HTTPException`, `status`). They receive plain arguments (schemas, IDs, an async DB session) and return plain Python objects or schemas.
- Services don't raise `HTTPException`. They raise domain exceptions (see below); mapping to HTTP status codes happens in `app/api/`.
- A service function's dependencies (DB session, other services, config) are passed in via constructor or function arguments, not imported as globals or pulled from FastAPI's DI container directly.

## Domain exceptions

- Define explicit exception classes per failure mode in `app/services/exceptions.py` (or per-module), e.g. `TaskNotFoundError`, `AuthenticationError`, `AuthorizationError`, `InvalidCredentialsError`, `EmailAlreadyRegisteredError`, subclassing a common `DomainError` base — never a bare `Exception` or `ValueError` for expected failure paths.
- Exception classes carry the context needed to build a response (e.g. the offending `task_id`) as attributes, not just a message string — except where that context is itself sensitive (`InvalidCredentialsError` deliberately carries no email/reason, so `app/main.py` can't accidentally leak which part of a login attempt failed).

## Structure

- One service class or module per aggregate/resource (`TaskService`, `UserService`), with methods named for the use case (`create_task`, `complete_task`), not generic CRUD verbs that hide intent when there's real business logic involved.
- Services depend on schemas (`app/schemas/`) for input/output shape and on models (`app/models/`) for persistence — never the other way around.
- Keep orchestration (multiple repository/service calls, transactions) in the service layer; keep single-table queries in a repository if one exists, otherwise directly in the service using the injected session.
