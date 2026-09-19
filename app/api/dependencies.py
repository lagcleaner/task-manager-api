from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.redis import get_redis_client
from app.core.security import AccessTokenClaims, InvalidTokenError, get_access_token_claims
from app.models.user import UserModel, UserRole
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.exceptions import AuthenticationError, AuthorizationError, RevokedTokenError
from app.services.task_list_service import TaskListService
from app.services.task_service import TaskService
from app.services.token_service import TokenService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_task_service(session: DbSession) -> AsyncGenerator[TaskService]:
    yield TaskService(session)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


async def get_task_list_service(session: DbSession) -> AsyncGenerator[TaskListService]:
    yield TaskListService(session)


TaskListServiceDep = Annotated[TaskListService, Depends(get_task_list_service)]


RedisDep = Annotated[Redis, Depends(get_redis_client)]


async def get_token_service(redis_client: RedisDep) -> AsyncGenerator[TokenService]:
    yield TokenService(redis_client)


TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


async def get_auth_service(
    session: DbSession, token_service: TokenServiceDep
) -> AsyncGenerator[AuthService]:
    yield AuthService(session, token_service)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_access_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    token_service: TokenServiceDep,
) -> AccessTokenClaims:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")

    try:
        claims = get_access_token_claims(credentials.credentials)
    except InvalidTokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    if await token_service.is_access_token_revoked(claims.jti):
        raise RevokedTokenError("Token revoked")

    return claims


CurrentAccessClaims = Annotated[AccessTokenClaims, Depends(get_current_access_claims)]


async def get_current_user(session: DbSession, claims: CurrentAccessClaims) -> UserModel:
    user = await UserRepository(session).get_by_id(claims.user_id)
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
