---
paths: ["app/schemas/**"]
---

# Pydantic schemas

Rules for Pydantic v2 models under `app/schemas/`.

## Model configuration

- Every schema uses `model_config = ConfigDict(...)`, never the old `class Config:` inner class.
- Response/read schemas (`*Read`) set `from_attributes=True` so they can be built from ORM instances.
- Prefer strict validation: `model_config = ConfigDict(strict=True)` unless a field intentionally needs coercion (e.g. parsing a date string) — if you relax it, comment why.
- Schemas representing an immutable value (e.g. an event payload, a read-only DTO) set `frozen=True`.

## Fields

- Every field with a constraint, default, or documentation need uses `Field(...)`: `Field(..., min_length=1, max_length=200, description="...")`, not a bare annotation with a raw default.
- No ambiguous primitives: don't type an amount of money, a duration, or an identifier as a bare `int`/`str`/`float` if a more specific type exists or can be expressed with `Annotated` + constraints. Use `EmailStr`, `AnyUrl`, `UUID`, `Literal[...]`, or an `Enum` instead of a loose `str` when the domain has a fixed vocabulary.
- Use `Literal` or `Enum` for status/kind fields (e.g. task status) — never a free-form string that's actually a closed set.

## Validators

- Use `@field_validator("field_name", mode="after")` (or `mode="before"` only when coercing raw input) — never the v1 `@validator`.
- Use `@model_validator(mode="after")` for cross-field invariants (e.g. `due_date >= created_at`).
- Validators raise `ValueError` with a clear message; do not swallow validation errors.

## Naming and shape

- One schema per intent per resource: `TaskCreate` (input, no `id`/timestamps), `TaskUpdate` (input, all fields optional), `TaskRead` (output, includes `id`/timestamps). Never reuse one schema across create/update/read by making fields optional out of convenience.
- Nested/related resources use their own `*Read` schema, not the raw ORM model or a `dict`.
