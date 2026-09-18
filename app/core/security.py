from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

_JWT_SUBJECT_CLAIM = "sub"


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(*, user_id: int) -> str:
    # Carries only the subject, never the role: authorization always re-reads
    # the role from the database (see require_role), so a still-valid token
    # can't keep granting access a since-revoked or since-demoted user lost.
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        _JWT_SUBJECT_CLAIM: str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or forged."""


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc
