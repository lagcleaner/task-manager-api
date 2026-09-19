from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import AdminUser, CurrentUser, TaskServiceDep
from app.schemas.common import ErrorResponse
from app.schemas.task import TaskAssigneeUpdate, TaskCreate, TaskRead, TaskStatusUpdate, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def create_task(data: TaskCreate, service: TaskServiceDep, _user: CurrentUser) -> TaskRead:
    task = await service.create_task(data)
    return TaskRead.model_validate(task)


@router.get(
    "",
    response_model=list[TaskRead],
    status_code=status.HTTP_200_OK,
    summary="List tasks",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def list_tasks(
    service: TaskServiceDep,
    _user: CurrentUser,
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=100, ge=1, le=500, description="Page size"),
) -> list[TaskRead]:
    tasks = await service.list_tasks(offset=offset, limit=limit)
    return [TaskRead.model_validate(task) for task in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Get a task by id",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_task(
    service: TaskServiceDep,
    _user: CurrentUser,
    task_id: int = Path(..., ge=1, description="Task identifier"),
) -> TaskRead:
    task = await service.get_task(task_id)
    return TaskRead.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Update a task",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def update_task(
    data: TaskUpdate,
    service: TaskServiceDep,
    _user: CurrentUser,
    task_id: int = Path(..., ge=1, description="Task identifier"),
) -> TaskRead:
    task = await service.update_task(task_id, data)
    return TaskRead.model_validate(task)


@router.patch(
    "/{task_id}/status",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Change task status",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def change_task_status(
    data: TaskStatusUpdate,
    service: TaskServiceDep,
    _user: CurrentUser,
    task_id: int = Path(..., ge=1, description="Task identifier"),
) -> TaskRead:
    task = await service.change_status(task_id, data.status)
    return TaskRead.model_validate(task)


@router.patch(
    "/{task_id}/assignee",
    response_model=TaskRead,
    status_code=status.HTTP_200_OK,
    summary="Assign a responsible user to a task",
    description="Pass `assignee_id: null` to unassign.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def assign_task(
    data: TaskAssigneeUpdate,
    service: TaskServiceDep,
    _user: CurrentUser,
    task_id: int = Path(..., ge=1, description="Task identifier"),
) -> TaskRead:
    task = await service.assign_task(task_id, data.assignee_id)
    return TaskRead.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    description="Requires the admin role.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def delete_task(
    service: TaskServiceDep,
    _admin: AdminUser,
    task_id: int = Path(..., ge=1, description="Task identifier"),
) -> None:
    await service.delete_task(task_id)
