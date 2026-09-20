from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel, TaskPriority, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: int) -> TaskModel | None:
        result = await self._session.execute(
            select(TaskModel).where(TaskModel.id == task_id, TaskModel.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_any(self, task_id: int) -> TaskModel | None:
        """Fetch a task regardless of soft-delete state — used by hard-delete paths."""
        return await self._session.get(TaskModel, task_id)

    async def list_all(self, *, offset: int = 0, limit: int = 100) -> list[TaskModel]:
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.deleted_at.is_(None))
            .order_by(TaskModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_deleted(self, *, offset: int = 0, limit: int = 100) -> list[TaskModel]:
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.deleted_at.is_not(None))
            .order_by(TaskModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_list_id(
        self,
        list_id: int,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[TaskModel]:
        query = select(TaskModel).where(
            TaskModel.list_id == list_id, TaskModel.deleted_at.is_(None)
        )
        if status is not None:
            query = query.where(TaskModel.status == status)
        if priority is not None:
            query = query.where(TaskModel.priority == priority)
        query = query.order_by(TaskModel.id).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_all_and_completed(self, list_id: int) -> tuple[int, int]:
        total_result = await self._session.execute(
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.list_id == list_id, TaskModel.deleted_at.is_(None))
        )
        total = total_result.scalar_one()

        completed_result = await self._session.execute(
            select(func.count())
            .select_from(TaskModel)
            .where(
                TaskModel.list_id == list_id,
                TaskModel.status == TaskStatus.COMPLETED,
                TaskModel.deleted_at.is_(None),
            )
        )
        completed = completed_result.scalar_one()

        return total, completed

    async def add(self, task: TaskModel) -> TaskModel:
        self._session.add(task)
        await self._session.flush()
        return task

    async def soft_delete(self, task: TaskModel) -> None:
        task.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

    async def soft_delete_by_list_id(self, list_id: int) -> None:
        """Cascade soft-delete: mark every active task in a list as deleted."""
        now = datetime.now(UTC).replace(tzinfo=None)
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.list_id == list_id, TaskModel.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self._session.flush()

    async def delete(self, task: TaskModel) -> None:
        await self._session.delete(task)
        await self._session.flush()
