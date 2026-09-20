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
    """Never called directly — exists only so `@limiter.limit(...)` registers
    `rate_limit_default` under this function's name in `limiter._dynamic_route_limits`.
    `default_rate_limit_dependency` below checks that registered limit directly instead
    of calling this wrapper, so it never touches `request.state._rate_limiting_complete`.
    """
    return None


async def default_rate_limit_dependency(request: Request) -> None:
    """No-op FastAPI dependency that enforces `rate_limit_default` via slowapi.

    This FastAPI version defers router inclusion (`_IncludedRouter`), so `app.routes`
    never exposes flat `APIRoute` objects with a real `.endpoint` — `SlowAPIMiddleware`'s
    route lookup can't find a handler and silently no-ops on every request. Wiring this as
    a `Depends()` on `app.include_router(...)` runs the check for every route under the
    `/v1` prefix without relying on the middleware's broken route matching.

    Calls `limiter._check_request_limit(...)` directly instead of invoking
    `_default_rate_limit_registration` through its `@limiter.limit(...)` wrapper: that
    wrapper sets `request.state._rate_limiting_complete = True` after checking, which
    would make slowapi skip the auth routes' own stricter `@limiter.limit(rate_limit_auth)`
    check downstream (dependencies run before the endpoint). `_check_request_limit` runs
    the identical lookup/evaluate logic keyed off the registration function's
    `__module__.__name__` without ever setting that flag, so both the default and the
    per-route auth limit apply independently, as intended.
    """
    limiter._check_request_limit(request, _default_rate_limit_registration, in_middleware=False)
