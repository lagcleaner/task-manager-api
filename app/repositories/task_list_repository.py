from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_list import TaskListModel


class TaskListRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, list_id: int, *, for_update: bool = False) -> TaskListModel | None:
        query = select(TaskListModel).where(
            TaskListModel.id == list_id, TaskListModel.deleted_at.is_(None)
        )
        if for_update:
            # Row lock: serializes against a concurrent soft-delete cascade (see
            # TaskListService.soft_delete_task_list) so a task/invitation create for this
            # list_id blocks until the cascade commits, instead of racing in between the
            # parent list's soft_delete and the cascade UPDATEs.
            query = query.with_for_update()
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_any(self, list_id: int) -> TaskListModel | None:
        """Fetch a task list regardless of soft-delete state — used by hard-delete paths."""
        return await self._session.get(TaskListModel, list_id)

    async def list_all(self, *, offset: int = 0, limit: int = 100) -> list[TaskListModel]:
        result = await self._session.execute(
            select(TaskListModel)
            .where(TaskListModel.deleted_at.is_(None))
            .order_by(TaskListModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_deleted(self, *, offset: int = 0, limit: int = 100) -> list[TaskListModel]:
        result = await self._session.execute(
            select(TaskListModel)
            .where(TaskListModel.deleted_at.is_not(None))
            .order_by(TaskListModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add(self, task_list: TaskListModel) -> TaskListModel:
        self._session.add(task_list)
        await self._session.flush()
        return task_list

    async def soft_delete(self, task_list: TaskListModel) -> None:
        task_list.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

    async def delete(self, task_list: TaskListModel) -> None:
        await self._session.delete(task_list)
        await self._session.flush()
