from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    # strict mode disabled: priority arrives as a JSON string and needs coercion into TaskPriority
    model_config = ConfigDict(strict=False)

    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: str | None = Field(
        default=None, max_length=2000, description="Optional task description"
    )
    list_id: int = Field(..., gt=0, description="Parent task list id")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    assignee_id: int | None = Field(default=None, gt=0, description="Responsible user id")


class TaskUpdate(BaseModel):
    # strict mode disabled: status arrives as a JSON string and needs coercion into TaskStatus
    model_config = ConfigDict(strict=False)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: TaskStatus | None = Field(default=None)
    priority: TaskPriority | None = Field(default=None)
    assignee_id: int | None = Field(default=None, gt=0, description="Responsible user id")


class TaskStatusUpdate(BaseModel):
    # strict mode disabled: status arrives as a JSON string and needs coercion into TaskStatus
    model_config = ConfigDict(strict=False)

    status: TaskStatus = Field(..., description="New task status")


class TaskAssigneeUpdate(BaseModel):
    assignee_id: int | None = Field(
        ..., description="User id to assign as responsible, or null to unassign"
    )


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    list_id: int
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime
