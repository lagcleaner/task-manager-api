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
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db_session  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.redis import get_redis_client  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # The limiter's in-memory storage is a module-level singleton shared by
    # every test in the process; without a reset, tests exercising
    # /v1/auth/* would trip each other's rate limit instead of the intended
    # per-test behavior. Rate limiting itself is covered by a dedicated test.
    limiter.reset()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
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
