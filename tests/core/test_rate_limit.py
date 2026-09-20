import pytest
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import rate_limit
from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "postgres_password": "x" * 20,
        "jwt_secret_key": "y" * 32,
        # Explicit default (no password) so this helper is deterministic
        # regardless of a local .env's REDIS_PASSWORD.
        "redis_password": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_build_storage_uri_without_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rate_limit,
        "_settings",
        _settings(redis_host="redis-host", redis_port=6380, redis_db=2),
    )

    uri = rate_limit._build_storage_uri()

    assert uri == "redis://redis-host:6380/2"


def test_build_storage_uri_with_password_embeds_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rate_limit,
        "_settings",
        _settings(
            redis_host="redis-host",
            redis_port=6380,
            redis_db=2,
            redis_password="s3cr3t-pass",
        ),
    )

    uri = rate_limit._build_storage_uri()

    assert uri == "redis://:s3cr3t-pass@redis-host:6380/2"


def test_build_storage_uri_quotes_password_with_reserved_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Generated passwords (e.g. base64-ish secrets) can contain "/", "+", "@",
    # ":" — reserved in a URI's userinfo component. Unescaped, they corrupt
    # host/port/db parsing on the receiving end (redis-py's Redis.from_url).
    monkeypatch.setattr(
        rate_limit,
        "_settings",
        _settings(
            redis_host="redis-host",
            redis_port=6380,
            redis_db=2,
            redis_password="wei/rd+pass@word:1",
        ),
    )

    uri = rate_limit._build_storage_uri()

    assert uri == "redis://:wei%2Frd%2Bpass%40word%3A1@redis-host:6380/2"

    # And it must actually parse back to the intended host/port/db, proving
    # the quoting round-trips correctly for the client that consumes it.
    from redis.connection import parse_url

    parsed = parse_url(uri)
    assert parsed["host"] == "redis-host"
    assert parsed["port"] == 6380
    assert parsed["db"] == 2
    assert parsed["password"] == "wei/rd+pass@word:1"


def test_limiter_storage_is_redis_backed_not_in_memory() -> None:
    # The module-level `limiter` was built with a storage_uri (see
    # app/core/rate_limit.py) rather than left to slowapi's in-memory
    # default. tests/conftest.py swaps its live `_storage`/`_limiter.storage`
    # per test to avoid needing a real Redis, but `_storage_uri` itself is
    # untouched, so it still proves production wiring passed a redis:// URI.
    assert rate_limit.limiter._storage_uri is not None
    assert rate_limit.limiter._storage_uri.startswith("redis://")

    # Independently, a Limiter built straight from the production
    # _build_storage_uri() resolves to slowapi's Redis backend class, not the
    # default in-memory one. No network I/O happens here: slowapi/limits only
    # connect lazily on the first actual command.
    uri = rate_limit._build_storage_uri()
    probe_limiter = Limiter(key_func=get_remote_address, storage_uri=uri)

    assert probe_limiter._storage.__class__.__name__ == "RedisStorage"


def test_two_limiters_built_from_same_settings_share_storage_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two independently-constructed Limiter instances pointed at the same
    # settings resolve to the same storage_uri, i.e. the same backing Redis
    # store/db — proof rate-limit state would be shared across replicas
    # instead of each holding its own in-memory counter.
    monkeypatch.setattr(
        rate_limit,
        "_settings",
        _settings(redis_host="shared-host", redis_port=6379, redis_db=5),
    )

    uri_a = rate_limit._build_storage_uri()
    uri_b = rate_limit._build_storage_uri()
    limiter_a = Limiter(key_func=get_remote_address, storage_uri=uri_a)
    limiter_b = Limiter(key_func=get_remote_address, storage_uri=uri_b)

    assert uri_a == uri_b == "redis://shared-host:6379/5"
    assert limiter_a._storage_uri == limiter_b._storage_uri
    assert limiter_a._storage.__class__ is limiter_b._storage.__class__ is not None
    assert limiter_a._storage.__class__.__name__ == "RedisStorage"
