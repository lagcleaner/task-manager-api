from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.schemas.auth import TokenPairResponse
from app.services.exceptions import InvalidRefreshTokenError

_REFRESH_SESSION_PREFIX = "refresh_session:"
_REVOKED_ACCESS_PREFIX = "revoked_access:"


def _ttl_seconds(expires_at: datetime) -> int:
    remaining = int((expires_at - datetime.now(UTC)).total_seconds())
    return max(remaining, 1)


class TokenService:
    """Owns the Redis-backed refresh-token allowlist and access-token blacklist."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def issue_token_pair(self, *, user_id: int) -> TokenPairResponse:
        settings = get_settings()
        access_token = create_access_token(user_id=user_id)
        refresh_token = create_refresh_token(user_id=user_id)
        payload = decode_refresh_token(refresh_token)
        await self._redis.set(
            f"{_REFRESH_SESSION_PREFIX}{payload['jti']}",
            str(user_id),
            ex=_ttl_seconds(datetime.fromtimestamp(payload["exp"], tz=UTC)),
        )
        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def rotate_refresh_token(self, refresh_token: str) -> TokenPairResponse:
        # Rotation: the presented refresh token must still be the single active
        # session for its jti. A second use of an already-rotated (or logged-out)
        # token — the replay case — finds no allowlist entry and is rejected.
        try:
            payload = decode_refresh_token(refresh_token)
        except InvalidTokenError as exc:
            raise InvalidRefreshTokenError("Refresh token invalid or expired") from exc

        jti = payload["jti"]
        user_id = int(payload["sub"])
        key = f"{_REFRESH_SESSION_PREFIX}{jti}"

        deleted = await self._redis.delete(key)
        if not deleted:
            raise InvalidRefreshTokenError("Refresh token invalid or expired")

        return await self.issue_token_pair(user_id=user_id)

    async def revoke_access_token(self, *, jti: str, expires_at: datetime) -> None:
        await self._redis.set(f"{_REVOKED_ACCESS_PREFIX}{jti}", "1", ex=_ttl_seconds(expires_at))

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        try:
            payload = decode_refresh_token(refresh_token)
        except InvalidTokenError:
            # Already invalid/expired: nothing left to revoke, logout still succeeds.
            return
        await self._redis.delete(f"{_REFRESH_SESSION_PREFIX}{payload['jti']}")

    async def is_access_token_revoked(self, jti: str) -> bool:
        return bool(await self._redis.exists(f"{_REVOKED_ACCESS_PREFIX}{jti}"))
