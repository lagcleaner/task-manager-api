import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskStatus
from app.models.task_list import TaskListModel
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import TaskListNotFoundError, TaskNotFoundError
from app.services.task_service import TaskService


async def _create_task_list(session: AsyncSession) -> TaskListModel:
    task_list = TaskListModel(name="Groceries", owner_id=1)
    session.add(task_list)
    await session.commit()
    await session.refresh(task_list)
    return task_list


async def test_create_task_persists_task(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)

    task = await service.create_task(TaskCreate(title="New task", list_id=task_list.id))

    assert task.id is not None
    assert task.title == "New task"
    assert task.list_id == task_list.id


async def test_create_task_raises_when_list_missing(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.create_task(TaskCreate(title="New task", list_id=999))


async def test_get_task_raises_when_missing(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    with pytest.raises(TaskNotFoundError):
        await service.get_task(1)


async def test_update_task_applies_partial_changes(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original", list_id=task_list.id))

    updated = await service.update_task(task.id, TaskUpdate(title="Renamed"))

    assert updated.title == "Renamed"


async def test_change_status_updates_task_status(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original", list_id=task_list.id))

    updated = await service.change_status(task.id, TaskStatus.IN_PROGRESS)

    assert updated.status == TaskStatus.IN_PROGRESS
