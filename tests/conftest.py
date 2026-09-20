import os
from collections.abc import AsyncGenerator

# Test-only placeholders, never used against a real database or service.
# Must be set before importing app.core.config / app.main so Settings() can load.
os.environ.setdefault("POSTGRES_PASSWORD", "test-only-placeholder-not-a-real-secret")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-signing-key-32-bytes-minimum-length")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from limits.storage import MemoryStorage
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.redis import get_redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserModel, UserRole  # noqa: E402


async def create_user(session: AsyncSession, email: str) -> UserModel:
    """Shared factory helper for service-layer tests that need a persisted user."""
    user = UserModel(email=email, hashed_password="not-a-real-hash", role=UserRole.USER)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # Production `limiter` is Redis-backed (see app/core/rate_limit.py) so
    # counts are shared across replicas, but tests don't run against a live
    # Redis. Swap in a fresh in-memory backend per test instead of calling
    # `.reset()` (which would issue real Redis commands) — same per-test
    # isolation, no live infra required. Rate limiting itself is covered by a
    # dedicated test; Redis wiring is covered by tests/core/test_rate_limit.py.
    fresh_storage = MemoryStorage()
    limiter._storage = fresh_storage
    limiter._limiter.storage = fresh_storage


def _mirror_postgres_partial_indexes_for_sqlite() -> None:
    """SQLAlchemy only honors `postgresql_where` when compiling DDL for the postgres
    dialect; a partial unique index defined that way (e.g. `InvitationModel`'s
    `uq_invitations_list_id_email_active`, see ADR-018) silently becomes a table-wide,
    non-partial index under sqlite -- this suite's in-memory test-DB dialect. The app is
    Postgres-only in production, but tests run against sqlite for speed, so mirror the
    postgres partial-index condition as `sqlite_where` too (sqlite supports partial
    indexes natively) to keep test-DB constraint semantics faithful to production.
    """
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            pg_where = index.dialect_options["postgresql"]["where"]
            if pg_where is not None:
                index.dialect_options["sqlite"]["where"] = pg_where


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    _mirror_postgres_partial_indexes_for_sqlite()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def redis_client() -> AsyncGenerator[Redis]:
    # In-memory fake, function-scoped so no state leaks between tests.
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(db_session: AsyncSession, redis_client: Redis) -> AsyncGenerator[AsyncClient]:
    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    def override_get_redis_client() -> Redis:
        return redis_client

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_redis_client] = override_get_redis_client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
