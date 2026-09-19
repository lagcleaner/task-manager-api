from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel, TaskPriority, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, task_id: int) -> TaskModel | None:
        return await self._session.get(TaskModel, task_id)

    async def list_all(self, *, offset: int = 0, limit: int = 100) -> list[TaskModel]:
        result = await self._session.execute(
            select(TaskModel).order_by(TaskModel.id).offset(offset).limit(limit)
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
        query = select(TaskModel).where(TaskModel.list_id == list_id)
        if status is not None:
            query = query.where(TaskModel.status == status)
        if priority is not None:
            query = query.where(TaskModel.priority == priority)
        query = query.order_by(TaskModel.id).offset(offset).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_all_and_completed(self, list_id: int) -> tuple[int, int]:
        total_result = await self._session.execute(
            select(func.count()).select_from(TaskModel).where(TaskModel.list_id == list_id)
        )
        total = total_result.scalar_one()

        completed_result = await self._session.execute(
            select(func.count())
            .select_from(TaskModel)
            .where(TaskModel.list_id == list_id, TaskModel.status == TaskStatus.COMPLETED)
        )
        completed = completed_result.scalar_one()

        return total, completed

    async def add(self, task: TaskModel) -> TaskModel:
        self._session.add(task)
        await self._session.flush()
        return task

    async def delete(self, task: TaskModel) -> None:
        await self._session.delete(task)
        await self._session.flush()
