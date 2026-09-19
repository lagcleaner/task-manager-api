from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import UserModel
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate
from app.services.exceptions import EmailAlreadyRegisteredError, InvalidCredentialsError


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = UserRepository(session)

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

    async def authenticate(self, data: LoginRequest) -> TokenResponse:
        settings = get_settings()
        user = await self._repository.get_by_email(data.email)
        # Same generic error whether the email is unknown or the password is wrong,
        # so responses can't be used to enumerate registered accounts.
        if user is None or not verify_password(
            data.password.get_secret_value(), user.hashed_password
        ):
            raise InvalidCredentialsError()

        token = create_access_token(user_id=user.id)
        return TokenResponse(
            access_token=token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
