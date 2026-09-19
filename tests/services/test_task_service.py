import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import TaskNotFoundError
from app.services.task_service import TaskService


async def test_create_task_persists_task(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    task = await service.create_task(TaskCreate(title="New task"))

    assert task.id is not None
    assert task.title == "New task"


async def test_get_task_raises_when_missing(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    with pytest.raises(TaskNotFoundError):
        await service.get_task(1)


async def test_update_task_applies_partial_changes(db_session: AsyncSession) -> None:
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original"))

    updated = await service.update_task(task.id, TaskUpdate(title="Renamed"))

    assert updated.title == "Renamed"
