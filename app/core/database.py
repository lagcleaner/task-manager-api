from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    # Lazy so importing `Base` (e.g. from Alembic, for metadata only) never
    # forces Settings() to load — Alembic connects with its own migrator
    # credentials and shouldn't need the app's runtime secrets at all.
    settings = get_settings()
    return create_async_engine(str(settings.database_url), echo=settings.database_echo)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session
