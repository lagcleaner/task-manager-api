from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskRead


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


class TaskListTasksRead(BaseModel):
    # Not built via model_validate(orm_instance): it's a synthetic composite of a filtered
    # task list plus a percentage computed over the whole (unfiltered) list, assembled by
    # the service/router — never a single ORM row, so from_attributes stays False.
    model_config = ConfigDict(from_attributes=False, frozen=True)

    tasks: list[TaskRead]
    completion_percentage: float = Field(
        ..., ge=0, le=100, description="Percentage of tasks in the list with status=completed"
    )
