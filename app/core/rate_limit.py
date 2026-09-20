from urllib.parse import quote

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
