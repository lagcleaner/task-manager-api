from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from app.core.security import decode_access_token, get_access_token_claims
from app.services.exceptions import InvalidRefreshTokenError
from app.services.token_service import TokenService


@pytest.fixture
def token_service(redis_client: Redis) -> TokenService:
    return TokenService(redis_client)


async def test_issue_token_pair_returns_access_and_refresh_token(
    token_service: TokenService,
) -> None:
    pair = await token_service.issue_token_pair(user_id=1)

    assert decode_access_token(pair.access_token)["sub"] == "1"
    assert pair.refresh_token
    assert pair.expires_in > 0


async def test_rotate_refresh_token_issues_new_pair(token_service: TokenService) -> None:
    first = await token_service.issue_token_pair(user_id=42)

    rotated = await token_service.rotate_refresh_token(first.refresh_token)

    assert rotated.refresh_token != first.refresh_token
    assert decode_access_token(rotated.access_token)["sub"] == "42"


async def test_rotate_refresh_token_rejects_reused_token(token_service: TokenService) -> None:
    first = await token_service.issue_token_pair(user_id=42)
    await token_service.rotate_refresh_token(first.refresh_token)

    with pytest.raises(InvalidRefreshTokenError):
        await token_service.rotate_refresh_token(first.refresh_token)


async def test_rotate_refresh_token_rejects_forged_token(token_service: TokenService) -> None:
    with pytest.raises(InvalidRefreshTokenError):
        await token_service.rotate_refresh_token("not-a-real-jwt")


async def test_revoke_access_token_marks_jti_as_revoked(token_service: TokenService) -> None:
    pair = await token_service.issue_token_pair(user_id=7)
    claims = get_access_token_claims(pair.access_token)

    assert await token_service.is_access_token_revoked(claims.jti) is False

    await token_service.revoke_access_token(jti=claims.jti, expires_at=claims.expires_at)

    assert await token_service.is_access_token_revoked(claims.jti) is True


async def test_revoke_refresh_token_prevents_future_rotation(token_service: TokenService) -> None:
    pair = await token_service.issue_token_pair(user_id=9)

    await token_service.revoke_refresh_token(pair.refresh_token)

    with pytest.raises(InvalidRefreshTokenError):
        await token_service.rotate_refresh_token(pair.refresh_token)


async def test_revoke_refresh_token_on_already_invalid_token_is_a_noop(
    token_service: TokenService,
) -> None:
    await token_service.revoke_refresh_token("not-a-real-jwt")


async def test_revoke_access_token_ttl_never_negative_for_near_expired_token(
    token_service: TokenService,
) -> None:
    almost_expired = datetime.now(UTC) + timedelta(milliseconds=1)

    await token_service.revoke_access_token(jti="near-expiry", expires_at=almost_expired)

    assert await token_service.is_access_token_revoked("near-expiry") is True
