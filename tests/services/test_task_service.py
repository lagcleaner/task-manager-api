import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskStatus
from app.models.task_list import TaskListModel
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import (
    NotOwnerError,
    TaskListNotFoundError,
    TaskNotFoundError,
    UserNotFoundError,
)
from app.services.task_service import TaskService
from tests.conftest import create_user as _create_user


async def _create_task_list(session: AsyncSession, owner_id: int = 1) -> TaskListModel:
    task_list = TaskListModel(name="Groceries", owner_id=owner_id)
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


async def test_create_task_raises_when_assignee_missing(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)

    with pytest.raises(UserNotFoundError):
        await service.create_task(
            TaskCreate(title="New task", list_id=task_list.id, assignee_id=999)
        )


async def test_update_task_raises_when_assignee_missing(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original", list_id=task_list.id))

    with pytest.raises(UserNotFoundError):
        await service.update_task(task.id, TaskUpdate(assignee_id=999))


async def test_assign_task_sets_assignee(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    user = await _create_user(db_session, "assignee@example.com")
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original", list_id=task_list.id))

    updated = await service.assign_task(task.id, user.id)

    assert updated.assignee_id == user.id


async def test_assign_task_unassigns_when_none(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    user = await _create_user(db_session, "assignee@example.com")
    service = TaskService(db_session)
    task = await service.create_task(
        TaskCreate(title="Original", list_id=task_list.id, assignee_id=user.id)
    )

    updated = await service.assign_task(task.id, None)

    assert updated.assignee_id is None


async def test_assign_task_raises_when_user_missing(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Original", list_id=task_list.id))

    with pytest.raises(UserNotFoundError):
        await service.assign_task(task.id, 999)


async def test_assign_task_raises_when_task_missing(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    with pytest.raises(TaskNotFoundError):
        await service.assign_task(999, None)


async def test_soft_delete_task_marks_deleted_for_list_owner(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner@example.com")
    task_list = await _create_task_list(db_session, owner_id=owner.id)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Temp", list_id=task_list.id))

    await service.soft_delete_task(task.id, owner)

    with pytest.raises(TaskNotFoundError):
        await service.get_task(task.id)


async def test_soft_delete_task_raises_not_owner_error_for_non_owner(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner2@example.com")
    other = await _create_user(db_session, "other@example.com")
    task_list = await _create_task_list(db_session, owner_id=owner.id)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Temp", list_id=task_list.id))

    with pytest.raises(NotOwnerError):
        await service.soft_delete_task(task.id, other)


async def test_soft_delete_task_raises_not_owner_error_for_assignee(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner3@example.com")
    assignee = await _create_user(db_session, "assignee3@example.com")
    task_list = await _create_task_list(db_session, owner_id=owner.id)
    service = TaskService(db_session)
    task = await service.create_task(
        TaskCreate(title="Temp", list_id=task_list.id, assignee_id=assignee.id)
    )

    # The assignee is not the owning list's owner, so they get no delete rights.
    with pytest.raises(NotOwnerError):
        await service.soft_delete_task(task.id, assignee)


async def test_soft_delete_task_raises_when_task_missing(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner4@example.com")
    service = TaskService(db_session)

    with pytest.raises(TaskNotFoundError):
        await service.soft_delete_task(999, owner)


async def test_permanent_delete_task_removes_active_task(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Temp", list_id=task_list.id))

    await service.permanent_delete_task(task.id)

    assert await TaskRepository(db_session).get_by_id_any(task.id) is None


async def test_permanent_delete_task_removes_already_soft_deleted_task(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner5@example.com")
    task_list = await _create_task_list(db_session, owner_id=owner.id)
    service = TaskService(db_session)
    task = await service.create_task(TaskCreate(title="Temp", list_id=task_list.id))
    await service.soft_delete_task(task.id, owner)

    await service.permanent_delete_task(task.id)

    assert await TaskRepository(db_session).get_by_id_any(task.id) is None


async def test_permanent_delete_task_raises_when_missing(db_session: AsyncSession) -> None:
    service = TaskService(db_session)

    with pytest.raises(TaskNotFoundError):
        await service.permanent_delete_task(999)


async def test_list_deleted_tasks_returns_soft_deleted_tasks(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner6@example.com")
    task_list = await _create_task_list(db_session, owner_id=owner.id)
    service = TaskService(db_session)
    kept = await service.create_task(TaskCreate(title="Kept", list_id=task_list.id))
    removed = await service.create_task(TaskCreate(title="Removed", list_id=task_list.id))
    await service.soft_delete_task(removed.id, owner)

    deleted_tasks = await service.list_deleted_tasks()

    assert [task.id for task in deleted_tasks] == [removed.id]
    assert kept.id not in [task.id for task in deleted_tasks]
