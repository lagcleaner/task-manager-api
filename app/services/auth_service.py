from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidTokenError,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import UserModel
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenPairResponse
from app.schemas.user import UserCreate
from app.services.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.services.token_service import TokenService


class AuthService:
    def __init__(self, session: AsyncSession, token_service: TokenService) -> None:
        self._session = session
        self._repository = UserRepository(session)
        self._token_service = token_service

    async def register_user(self, data: UserCreate) -> UserModel:
        existing = await self._repository.get_by_email(data.email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(data.email)

        user = UserModel(
            email=data.email,
            hashed_password=hash_password(data.password.get_secret_value()),
        )
        user = await self._repository.add(user)
        await self._session.commit()
        return user

    async def authenticate(self, data: LoginRequest) -> TokenPairResponse:
        user = await self._repository.get_by_email(data.email)
        # Same generic error whether the email is unknown or the password is wrong,
        # so responses can't be used to enumerate registered accounts.
        if user is None or not verify_password(
            data.password.get_secret_value(), user.hashed_password
        ):
            raise InvalidCredentialsError()

        return await self._token_service.issue_token_pair(user_id=user.id)

    async def refresh(self, refresh_token: str) -> TokenPairResponse:
        try:
            payload = decode_refresh_token(refresh_token)
        except InvalidTokenError as exc:
            raise InvalidRefreshTokenError("Refresh token invalid or expired") from exc

        # Reject up front for a deleted user, rather than after rotation has
        # already burned the presented refresh token for no benefit.
        user = await self._repository.get_by_id(int(payload["sub"]))
        if user is None:
            raise InvalidRefreshTokenError("Refresh token invalid or expired")

        return await self._token_service.rotate_refresh_token(refresh_token)

    async def logout(
        self, *, access_jti: str, access_expires_at: datetime, refresh_token: str | None
    ) -> None:
        await self._token_service.revoke_access_token(jti=access_jti, expires_at=access_expires_at)
        if refresh_token is not None:
            await self._token_service.revoke_refresh_token(refresh_token)
