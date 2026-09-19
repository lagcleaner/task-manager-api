import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate
from app.schemas.task_list import TaskListCreate, TaskListUpdate
from app.services.exceptions import TaskListNotFoundError
from app.services.task_list_service import TaskListService
from app.services.task_service import TaskService


async def test_list_tasks_computes_completion_percentage(db_session: AsyncSession) -> None:
    task_list_service = TaskListService(db_session)
    task_service = TaskService(db_session)
    task_list = await task_list_service.create_task_list(TaskListCreate(name="List"), owner_id=1)
    completed = await task_service.create_task(
        TaskCreate(title="One", list_id=task_list.id, priority=TaskPriority.HIGH)
    )
    await task_service.create_task(TaskCreate(title="Two", list_id=task_list.id))
    await task_service.create_task(TaskCreate(title="Three", list_id=task_list.id))
    await task_service.create_task(TaskCreate(title="Four", list_id=task_list.id))
    await task_service.change_status(completed.id, TaskStatus.COMPLETED)

    tasks, completion_percentage = await task_list_service.list_tasks(task_list.id)

    assert len(tasks) == 4
    assert completion_percentage == 25.0


async def test_list_tasks_returns_zero_percentage_when_list_empty(
    db_session: AsyncSession,
) -> None:
    task_list_service = TaskListService(db_session)
    task_list = await task_list_service.create_task_list(TaskListCreate(name="Empty"), owner_id=1)

    tasks, completion_percentage = await task_list_service.list_tasks(task_list.id)

    assert tasks == []
    assert completion_percentage == 0.0


async def test_list_tasks_filters_by_priority_without_affecting_percentage(
    db_session: AsyncSession,
) -> None:
    task_list_service = TaskListService(db_session)
    task_service = TaskService(db_session)
    task_list = await task_list_service.create_task_list(TaskListCreate(name="List"), owner_id=1)
    completed = await task_service.create_task(TaskCreate(title="One", list_id=task_list.id))
    await task_service.create_task(
        TaskCreate(title="Two", list_id=task_list.id, priority=TaskPriority.HIGH)
    )
    await task_service.change_status(completed.id, TaskStatus.COMPLETED)

    tasks, completion_percentage = await task_list_service.list_tasks(
        task_list.id, priority=TaskPriority.HIGH
    )

    assert len(tasks) == 1
    assert tasks[0].priority == TaskPriority.HIGH
    assert completion_percentage == 50.0


async def test_list_tasks_raises_when_list_missing(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.list_tasks(999)


async def test_create_task_list_persists_task_list(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)

    task_list = await service.create_task_list(TaskListCreate(name="New list"), owner_id=1)

    assert task_list.id is not None
    assert task_list.name == "New list"
    assert task_list.owner_id == 1


async def test_get_task_list_raises_when_missing(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.get_task_list(1)


async def test_update_task_list_applies_partial_changes(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)
    task_list = await service.create_task_list(TaskListCreate(name="Original"), owner_id=1)

    updated = await service.update_task_list(task_list.id, TaskListUpdate(name="Renamed"))

    assert updated.name == "Renamed"
