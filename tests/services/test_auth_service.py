import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, get_access_token_claims
from app.schemas.auth import LoginRequest
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.services.exceptions import InvalidCredentialsError, InvalidRefreshTokenError
from app.services.token_service import TokenService

_PASSWORD = "correct-horse-1"


@pytest.fixture
def auth_service(db_session: AsyncSession, redis_client: Redis) -> AuthService:
    return AuthService(db_session, TokenService(redis_client))


async def test_authenticate_returns_token_pair_for_valid_credentials(
    auth_service: AuthService,
) -> None:
    await auth_service.register_user(UserCreate(email="user@example.com", password=_PASSWORD))

    pair = await auth_service.authenticate(
        LoginRequest(email="user@example.com", password=_PASSWORD)
    )

    assert decode_access_token(pair.access_token)["sub"]
    assert pair.refresh_token


async def test_authenticate_raises_for_wrong_password(auth_service: AuthService) -> None:
    await auth_service.register_user(UserCreate(email="user2@example.com", password=_PASSWORD))

    with pytest.raises(InvalidCredentialsError):
        await auth_service.authenticate(
            LoginRequest(email="user2@example.com", password="wrong-password-1")
        )


async def test_refresh_rotates_tokens(auth_service: AuthService) -> None:
    await auth_service.register_user(UserCreate(email="user3@example.com", password=_PASSWORD))
    pair = await auth_service.authenticate(
        LoginRequest(email="user3@example.com", password=_PASSWORD)
    )

    rotated = await auth_service.refresh(pair.refresh_token)

    assert rotated.refresh_token != pair.refresh_token


async def test_refresh_rejects_already_rotated_token(auth_service: AuthService) -> None:
    await auth_service.register_user(UserCreate(email="user4@example.com", password=_PASSWORD))
    pair = await auth_service.authenticate(
        LoginRequest(email="user4@example.com", password=_PASSWORD)
    )
    await auth_service.refresh(pair.refresh_token)

    with pytest.raises(InvalidRefreshTokenError):
        await auth_service.refresh(pair.refresh_token)


async def test_refresh_rejects_token_for_deleted_user(
    auth_service: AuthService, db_session: AsyncSession
) -> None:
    user = await auth_service.register_user(
        UserCreate(email="user5@example.com", password=_PASSWORD)
    )
    pair = await auth_service.authenticate(
        LoginRequest(email="user5@example.com", password=_PASSWORD)
    )
    await db_session.delete(user)
    await db_session.commit()

    with pytest.raises(InvalidRefreshTokenError):
        await auth_service.refresh(pair.refresh_token)


async def test_logout_revokes_access_and_refresh_tokens(auth_service: AuthService) -> None:
    await auth_service.register_user(UserCreate(email="user6@example.com", password=_PASSWORD))
    pair = await auth_service.authenticate(
        LoginRequest(email="user6@example.com", password=_PASSWORD)
    )
    claims = get_access_token_claims(pair.access_token)

    await auth_service.logout(
        access_jti=claims.jti,
        access_expires_at=claims.expires_at,
        refresh_token=pair.refresh_token,
    )

    with pytest.raises(InvalidRefreshTokenError):
        await auth_service.refresh(pair.refresh_token)
