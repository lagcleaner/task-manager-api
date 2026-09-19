from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_list import TaskListModel


class TaskListRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, list_id: int) -> TaskListModel | None:
        return await self._session.get(TaskListModel, list_id)

    async def list_all(self, *, offset: int = 0, limit: int = 100) -> list[TaskListModel]:
        result = await self._session.execute(
            select(TaskListModel).order_by(TaskListModel.id).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def add(self, task_list: TaskListModel) -> TaskListModel:
        self._session.add(task_list)
        await self._session.flush()
        return task_list

    async def delete(self, task_list: TaskListModel) -> None:
        await self._session.delete(task_list)
        await self._session.flush()
