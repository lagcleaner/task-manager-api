from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_list import TaskListModel
from app.repositories.task_list_repository import TaskListRepository


async def _create_task_list(session: AsyncSession, name: str = "Groceries") -> TaskListModel:
    task_list = TaskListModel(name=name, owner_id=1)
    session.add(task_list)
    await session.commit()
    await session.refresh(task_list)
    return task_list


async def test_soft_delete_sets_deleted_at(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    repository = TaskListRepository(db_session)

    await repository.soft_delete(task_list)

    assert task_list.deleted_at is not None


async def test_soft_delete_excludes_row_from_get_by_id(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    repository = TaskListRepository(db_session)

    await repository.soft_delete(task_list)

    assert await repository.get_by_id(task_list.id) is None


async def test_soft_delete_excludes_row_from_list_all(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    repository = TaskListRepository(db_session)

    await repository.soft_delete(task_list)

    assert await repository.list_all() == []


async def test_get_by_id_any_returns_row_after_soft_delete(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    repository = TaskListRepository(db_session)

    await repository.soft_delete(task_list)
    found = await repository.get_by_id_any(task_list.id)

    assert found is not None
    assert found.id == task_list.id
    assert found.deleted_at is not None


async def test_list_deleted_returns_soft_deleted_rows(db_session: AsyncSession) -> None:
    active = await _create_task_list(db_session, "Active")
    deleted = await _create_task_list(db_session, "Deleted")
    repository = TaskListRepository(db_session)

    await repository.soft_delete(deleted)
    deleted_lists = await repository.list_deleted()

    assert [task_list.id for task_list in deleted_lists] == [deleted.id]
    assert active.id not in [task_list.id for task_list in deleted_lists]
