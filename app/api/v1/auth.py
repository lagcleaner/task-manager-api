from fastapi import APIRouter, Request, status

from app.api.dependencies import AuthServiceDep
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.auth import LoginRequest, TokenResponse
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
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange credentials for a bearer access token",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def login(request: Request, data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.authenticate(data)
