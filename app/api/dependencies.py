from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import UserModel, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.exceptions import AuthenticationError, AuthorizationError
from app.services.task_service import TaskService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_task_service(session: DbSession) -> AsyncGenerator[TaskService]:
    yield TaskService(session)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


async def get_auth_service(session: DbSession) -> AsyncGenerator[AuthService]:
    yield AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UserModel:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    user_id = int(payload["sub"])
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User no longer exists")
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole) -> Callable[[UserModel], UserModel]:
    def _check(user: CurrentUser) -> UserModel:
        if user.role not in allowed_roles:
            raise AuthorizationError(", ".join(role.value for role in allowed_roles))
        return user

    return _check


# Module-level so route signatures reference a name, not a bare `Depends(...)` call
# (keeps ruff's B008 happy and matches the *Dep alias pattern used everywhere else).
AdminUser = Annotated[UserModel, Depends(require_role(UserRole.ADMIN))]
