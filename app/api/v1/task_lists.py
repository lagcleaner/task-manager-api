from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import AdminUser, CurrentUser, TaskListServiceDep
from app.schemas.common import ErrorResponse
from app.schemas.task_list import TaskListCreate, TaskListRead, TaskListUpdate

router = APIRouter(prefix="/task-lists", tags=["task-lists"])


@router.post(
    "",
    response_model=TaskListRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task list",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def create_task_list(
    data: TaskListCreate, service: TaskListServiceDep, user: CurrentUser
) -> TaskListRead:
    task_list = await service.create_task_list(data, owner_id=user.id)
    return TaskListRead.model_validate(task_list)


@router.get(
    "",
    response_model=list[TaskListRead],
    status_code=status.HTTP_200_OK,
    summary="List task lists",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def list_task_lists(
    service: TaskListServiceDep,
    _user: CurrentUser,
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=100, ge=1, le=500, description="Page size"),
) -> list[TaskListRead]:
    task_lists = await service.list_task_lists(offset=offset, limit=limit)
    return [TaskListRead.model_validate(task_list) for task_list in task_lists]


@router.get(
    "/{list_id}",
    response_model=TaskListRead,
    status_code=status.HTTP_200_OK,
    summary="Get a task list by id",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def get_task_list(
    service: TaskListServiceDep,
    _user: CurrentUser,
    list_id: int = Path(..., ge=1, description="Task list identifier"),
) -> TaskListRead:
    task_list = await service.get_task_list(list_id)
    return TaskListRead.model_validate(task_list)


@router.patch(
    "/{list_id}",
    response_model=TaskListRead,
    status_code=status.HTTP_200_OK,
    summary="Update a task list",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def update_task_list(
    data: TaskListUpdate,
    service: TaskListServiceDep,
    _user: CurrentUser,
    list_id: int = Path(..., ge=1, description="Task list identifier"),
) -> TaskListRead:
    task_list = await service.update_task_list(list_id, data)
    return TaskListRead.model_validate(task_list)


@router.delete(
    "/{list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task list",
    description="Requires the admin role.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
async def delete_task_list(
    service: TaskListServiceDep,
    _admin: AdminUser,
    list_id: int = Path(..., ge=1, description="Task list identifier"),
) -> None:
    await service.delete_task_list(list_id)
