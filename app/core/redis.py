from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> Redis:
    # Lazy, same reasoning as app/core/database.py's get_engine(): building the
    # client at import time would force Settings() to load wherever this module
    # is merely imported (e.g. for typing).
    settings = get_settings()
    password = settings.redis_password.get_secret_value() if settings.redis_password else None
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
    )
