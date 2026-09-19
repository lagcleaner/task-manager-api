from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(..., description="Email address to invite")


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    list_id: int
    email: EmailStr
    invited_by_id: int
    created_at: datetime
