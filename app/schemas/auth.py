from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(..., description="Account email")
    password: SecretStr = Field(..., description="Account password")


class TokenPairResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    refresh_token: SecretStr = Field(..., description="Refresh token issued at login")


class LogoutRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    refresh_token: SecretStr | None = Field(
        default=None,
        description="Refresh token to revoke alongside the current access token",
    )
