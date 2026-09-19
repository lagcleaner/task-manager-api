import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings

_JWT_SUBJECT_CLAIM = "sub"
_JWT_ID_CLAIM = "jti"
_JWT_TYPE_CLAIM = "type"

TokenType = Literal["access", "refresh"]
_ACCESS_TOKEN_TYPE: TokenType = "access"
_REFRESH_TOKEN_TYPE: TokenType = "refresh"


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    jti: str
    expires_at: datetime


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(*, user_id: int, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        _JWT_SUBJECT_CLAIM: str(user_id),
        _JWT_ID_CLAIM: str(uuid.uuid4()),
        _JWT_TYPE_CLAIM: token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(*, user_id: int) -> str:
    # Carries only the subject (+ jti/type), never the role: authorization always
    # re-reads the role from the database (see require_role), so a still-valid
    # token can't keep granting access a since-revoked or since-demoted user lost.
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        token_type=_ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: int) -> str:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        token_type=_REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, forged, or the wrong type."""


def _decode(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    if payload.get(_JWT_TYPE_CLAIM) != expected_type:
        raise InvalidTokenError("Invalid or expired token")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode(token, expected_type=_ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode(token, expected_type=_REFRESH_TOKEN_TYPE)


def get_access_token_claims(token: str) -> AccessTokenClaims:
    payload = decode_access_token(token)
    return AccessTokenClaims(
        user_id=int(payload[_JWT_SUBJECT_CLAIM]),
        jti=payload[_JWT_ID_CLAIM],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )
