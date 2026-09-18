import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models.user import UserRole

_PASSWORD_MIN_LENGTH = 12
_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")


class UserCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(..., description="Unique account email")
    password: SecretStr = Field(..., description="Plaintext password, hashed on receipt")

    @field_validator("password")
    @classmethod
    def _enforce_password_strength(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < _PASSWORD_MIN_LENGTH:
            raise ValueError(f"password must be at least {_PASSWORD_MIN_LENGTH} characters")
        if not (_HAS_LETTER.search(raw) and _HAS_DIGIT.search(raw)):
            raise ValueError("password must contain at least one letter and one digit")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime
