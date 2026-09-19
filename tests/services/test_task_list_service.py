import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.task_list import TaskListCreate, TaskListUpdate
from app.services.exceptions import TaskListNotFoundError
from app.services.task_list_service import TaskListService


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
