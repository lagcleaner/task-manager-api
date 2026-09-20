from urllib.parse import quote

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()


def _build_storage_uri() -> str:
    # Same password-handling pattern as app/core/redis.py: unwrapped only
    # here, at the point of building the URI, never stored beyond this call.
    # Quoted because a generated password can contain reserved URI characters
    # (e.g. "/", "@", ":") that would otherwise corrupt host/port/db parsing
    # on the receiving end (redis-py's `Redis.from_url`).
    password = _settings.redis_password.get_secret_value() if _settings.redis_password else None
    auth = f":{quote(password, safe='')}@" if password else ""
    return f"redis://{auth}{_settings.redis_host}:{_settings.redis_port}/{_settings.redis_db}"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    storage_uri=_build_storage_uri(),
)


@limiter.limit(lambda: get_settings().rate_limit_default)
async def _default_rate_limit_registration(request: Request) -> None:
    """Never called directly — only decorated so its limit gets registered
    for `default_rate_limit_dependency` to check."""
    return None


async def default_rate_limit_dependency(request: Request) -> None:
    """Replaces `SlowAPIMiddleware`, which can't find routes on this FastAPI
    version. Checks the limit directly instead of via the decorator above, so
    it doesn't mark the request complete and skip the auth routes' own limit.
    """
    limiter._check_request_limit(request, _default_rate_limit_registration, in_middleware=False)
