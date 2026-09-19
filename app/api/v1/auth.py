from fastapi import APIRouter, Request, status

from app.api.dependencies import AuthServiceDep, CurrentAccessClaims
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenPairResponse
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={status.HTTP_409_CONFLICT: {"model": ErrorResponse}},
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def register(request: Request, data: UserCreate, service: AuthServiceDep) -> UserRead:
    user = await service.register_user(data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange credentials for an access/refresh token pair",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def login(request: Request, data: LoginRequest, service: AuthServiceDep) -> TokenPairResponse:
    return await service.authenticate(data)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new token pair",
    description="Rotates the refresh token: the presented one is invalidated immediately.",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def refresh(
    request: Request, data: RefreshRequest, service: AuthServiceDep
) -> TokenPairResponse:
    return await service.refresh(data.refresh_token.get_secret_value())


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current access token and, if provided, the refresh token",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def logout(
    request: Request,
    claims: CurrentAccessClaims,
    data: LogoutRequest,
    service: AuthServiceDep,
) -> None:
    refresh_token = data.refresh_token.get_secret_value() if data.refresh_token else None
    await service.logout(
        access_jti=claims.jti,
        access_expires_at=claims.expires_at,
        refresh_token=refresh_token,
    )
