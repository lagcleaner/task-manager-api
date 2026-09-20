from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel
from app.models.task_list import TaskListModel
from app.repositories.task_repository import TaskRepository


async def _create_task_list(session: AsyncSession) -> TaskListModel:
    task_list = TaskListModel(name="Groceries", owner_id=1)
    session.add(task_list)
    await session.commit()
    await session.refresh(task_list)
    return task_list


async def _create_task(session: AsyncSession, list_id: int, title: str = "Task") -> TaskModel:
    task = TaskModel(title=title, list_id=list_id)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def test_soft_delete_sets_deleted_at(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    task = await _create_task(db_session, task_list.id)
    repository = TaskRepository(db_session)

    await repository.soft_delete(task)

    assert task.deleted_at is not None


async def test_soft_delete_excludes_row_from_get_by_id(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    task = await _create_task(db_session, task_list.id)
    repository = TaskRepository(db_session)

    await repository.soft_delete(task)

    assert await repository.get_by_id(task.id) is None


async def test_soft_delete_excludes_row_from_list_all(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    task = await _create_task(db_session, task_list.id)
    repository = TaskRepository(db_session)

    await repository.soft_delete(task)

    assert await repository.list_all() == []


async def test_get_by_id_any_returns_row_after_soft_delete(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    task = await _create_task(db_session, task_list.id)
    repository = TaskRepository(db_session)

    await repository.soft_delete(task)
    found = await repository.get_by_id_any(task.id)

    assert found is not None
    assert found.id == task.id
    assert found.deleted_at is not None


async def test_list_deleted_returns_soft_deleted_rows(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    active = await _create_task(db_session, task_list.id, "Active")
    deleted = await _create_task(db_session, task_list.id, "Deleted")
    repository = TaskRepository(db_session)

    await repository.soft_delete(deleted)
    deleted_tasks = await repository.list_deleted()

    assert [task.id for task in deleted_tasks] == [deleted.id]
    assert active.id not in [task.id for task in deleted_tasks]


async def test_soft_delete_by_list_id_cascades_to_child_tasks(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    other_list = await _create_task_list(db_session)
    task_one = await _create_task(db_session, task_list.id, "One")
    task_two = await _create_task(db_session, task_list.id, "Two")
    other_task = await _create_task(db_session, other_list.id, "Other")
    repository = TaskRepository(db_session)

    await repository.soft_delete_by_list_id(task_list.id)

    assert await repository.get_by_id(task_one.id) is None
    assert await repository.get_by_id(task_two.id) is None
    assert await repository.get_by_id(other_task.id) is not None
