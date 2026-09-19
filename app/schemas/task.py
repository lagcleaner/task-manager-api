from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: str | None = Field(
        default=None, max_length=2000, description="Optional task description"
    )
    list_id: int = Field(..., gt=0, description="Parent task list id")


class TaskUpdate(BaseModel):
    # strict mode disabled: status arrives as a JSON string and needs coercion into TaskStatus
    model_config = ConfigDict(strict=False)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = Field(default=None)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    list_id: int
    created_at: datetime
    updated_at: datetime
