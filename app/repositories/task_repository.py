from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel


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

    async def add(self, task: TaskModel) -> TaskModel:
        self._session.add(task)
        await self._session.flush()
        return task

    async def delete(self, task: TaskModel) -> None:
        await self._session.delete(task)
        await self._session.flush()
