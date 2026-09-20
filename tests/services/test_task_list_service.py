import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskPriority, TaskStatus
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.task_list_repository import TaskListRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate
from app.schemas.task_list import TaskListCreate, TaskListUpdate
from app.services.exceptions import NotOwnerError, TaskListNotFoundError
from app.services.notification_service import NotificationService
from app.services.task_list_service import TaskListService
from app.services.task_service import TaskService
from tests.conftest import create_user as _create_user


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


async def test_soft_delete_task_list_marks_deleted_for_owner(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner@example.com")
    service = TaskListService(db_session)
    task_list = await service.create_task_list(TaskListCreate(name="Temp"), owner_id=owner.id)

    await service.soft_delete_task_list(task_list.id, owner)

    with pytest.raises(TaskListNotFoundError):
        await service.get_task_list(task_list.id)


async def test_soft_delete_task_list_raises_not_owner_error_for_non_owner(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner2@example.com")
    other = await _create_user(db_session, "other@example.com")
    service = TaskListService(db_session)
    task_list = await service.create_task_list(TaskListCreate(name="Temp"), owner_id=owner.id)

    with pytest.raises(NotOwnerError):
        await service.soft_delete_task_list(task_list.id, other)


async def test_soft_delete_task_list_raises_when_missing(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner3@example.com")
    service = TaskListService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.soft_delete_task_list(999, owner)


async def test_soft_delete_task_list_cascades_to_tasks_and_invitations(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner4@example.com")
    task_list_service = TaskListService(db_session)
    task_service = TaskService(db_session)
    notification_service = NotificationService(db_session)
    task_list = await task_list_service.create_task_list(
        TaskListCreate(name="Temp"), owner_id=owner.id
    )
    task = await task_service.create_task(TaskCreate(title="Child", list_id=task_list.id))
    invitation = await notification_service.send_task_list_invitation(
        task_list.id, "invitee@example.com", invited_by_id=owner.id
    )

    await task_list_service.soft_delete_task_list(task_list.id, owner)

    assert await TaskRepository(db_session).get_by_id(task.id) is None
    invitations = await InvitationRepository(db_session).list_by_list_id(task_list.id)
    assert next(i for i in invitations if i.id == invitation.id).deleted_at is not None


async def test_permanent_delete_task_list_removes_active_list(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)
    task_list = await service.create_task_list(TaskListCreate(name="Temp"), owner_id=1)

    await service.permanent_delete_task_list(task_list.id)

    assert await TaskListRepository(db_session).get_by_id_any(task_list.id) is None


async def test_permanent_delete_task_list_removes_already_soft_deleted_list(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner5@example.com")
    service = TaskListService(db_session)
    task_list = await service.create_task_list(TaskListCreate(name="Temp"), owner_id=owner.id)
    await service.soft_delete_task_list(task_list.id, owner)

    await service.permanent_delete_task_list(task_list.id)

    assert await TaskListRepository(db_session).get_by_id_any(task_list.id) is None


async def test_permanent_delete_task_list_raises_when_missing(db_session: AsyncSession) -> None:
    service = TaskListService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.permanent_delete_task_list(999)


async def test_list_deleted_task_lists_returns_soft_deleted_lists(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner6@example.com")
    service = TaskListService(db_session)
    kept = await service.create_task_list(TaskListCreate(name="Kept"), owner_id=owner.id)
    removed = await service.create_task_list(TaskListCreate(name="Removed"), owner_id=owner.id)
    await service.soft_delete_task_list(removed.id, owner)

    deleted_lists = await service.list_deleted_task_lists()

    assert [task_list.id for task_list in deleted_lists] == [removed.id]
    assert kept.id not in [task_list.id for task_list in deleted_lists]
