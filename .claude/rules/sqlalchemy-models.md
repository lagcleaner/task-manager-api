---
paths: ["app/models/**"]
---

# SQLAlchemy models

Rules for SQLAlchemy 2.0 async ORM models under `app/models/`.

## Declarative style

- Use SQLAlchemy 2.0 typed declarative style exclusively: `Mapped[...]` + `mapped_column(...)`, never the legacy `Column(...)` class-attribute style.
- Every model inherits from a shared `Base` (declarative base defined once in `app/models/base.py` or `app/core/db.py`), not redefined per file.
- Table names are explicit and plural snake_case via `__tablename__` (e.g. `"tasks"`, `"users"`), not inferred implicitly.

## Type hints and columns

- Every `Mapped[...]` annotation matches the actual nullability: `Mapped[str]` for `NOT NULL`, `Mapped[str | None]` for nullable columns — never a mismatch that hides null handling bugs.
- Primary keys: `Mapped[int] = mapped_column(primary_key=True)` (or `UUID` if the project uses UUID PKs) — be consistent across all models.
- Timestamps (`created_at`, `updated_at`) use `Mapped[datetime]` with `server_default=func.now()` (and `onupdate=func.now()` for `updated_at`), not application-side `datetime.utcnow()` defaults.
- Foreign keys use `mapped_column(ForeignKey("table.column"))` with an explicit `Mapped[int]` (or the FK's actual type), never inferred.

## Relationships

- Every `relationship()` declares `Mapped[...]` on both sides when the relationship is bidirectional, with explicit `back_populates` (not the implicit `backref`).
- Set `lazy=` explicitly when the default lazy-loading behavior would cause an async I/O error (e.g. `lazy="selectin"` for relationships accessed after the session context, since implicit lazy-load doesn't work with async sessions).
- Cascade behavior (`cascade="all, delete-orphan"`) is explicit on parent-owns-child relationships, not left to database-level defaults.

## Async usage

- Models themselves stay ORM-only; session handling and queries belong in `app/services/` or a repository layer, not in the model file.
- No blocking/sync SQLAlchemy calls anywhere in code paths that use the async engine.
