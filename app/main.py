import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import request_id_middleware, security_headers_middleware
from app.core.rate_limit import limiter
from app.services.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RevokedTokenError,
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)

settings = get_settings()

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.project_name,
    debug=settings.debug,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Bearer-token auth carries no cookies, so credentialed CORS is never needed here.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(request_id_middleware)

app.include_router(api_router, prefix=settings.api_v1_prefix)


def _error(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"detail": {"code": code, "message": message}}


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    return JSONResponse(_error("task_not_found", str(exc)), status_code=status.HTTP_404_NOT_FOUND)


@app.exception_handler(TaskListNotFoundError)
async def task_list_not_found_handler(request: Request, exc: TaskListNotFoundError) -> JSONResponse:
    return JSONResponse(
        _error("task_list_not_found", str(exc)), status_code=status.HTTP_404_NOT_FOUND
    )


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(_error("user_not_found", str(exc)), status_code=status.HTTP_404_NOT_FOUND)


@app.exception_handler(EmailAlreadyRegisteredError)
async def email_already_registered_handler(
    request: Request, exc: EmailAlreadyRegisteredError
) -> JSONResponse:
    return JSONResponse(
        _error("email_already_registered", str(exc)), status_code=status.HTTP_409_CONFLICT
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(
    request: Request, exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(
        _error("invalid_credentials", str(exc)), status_code=status.HTTP_401_UNAUTHORIZED
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        _error("authentication_required", "Authentication required"),
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(RevokedTokenError)
async def revoked_token_handler(request: Request, exc: RevokedTokenError) -> JSONResponse:
    return JSONResponse(
        _error("token_revoked", "Token has been revoked"),
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(InvalidRefreshTokenError)
async def invalid_refresh_token_handler(
    request: Request, exc: InvalidRefreshTokenError
) -> JSONResponse:
    return JSONResponse(
        _error("invalid_refresh_token", "Refresh token invalid or expired"),
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return JSONResponse(
        _error("forbidden", "Insufficient permissions"), status_code=status.HTTP_403_FORBIDDEN
    )


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    # Catch-all for any domain error without a dedicated handler above: still a 4xx-shaped
    # generic message, never str(exc) verbatim, so a future exception subclass can't
    # accidentally leak internal details just by being raised.
    logger.warning("Unhandled domain error: %s", type(exc).__name__)
    return JSONResponse(
        _error("bad_request", "Request could not be processed"),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled exception for request_id=%s", request_id)
    return JSONResponse(
        _error("internal_server_error", "An unexpected error occurred"),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
