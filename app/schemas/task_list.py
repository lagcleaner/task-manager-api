from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskListCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=200, description="Task list name")
    description: str | None = Field(
        default=None, max_length=2000, description="Optional task list description"
    )


class TaskListUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class TaskListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime
    updated_at: datetime
