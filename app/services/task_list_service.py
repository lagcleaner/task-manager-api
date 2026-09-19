from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel, TaskPriority, TaskStatus
from app.models.task_list import TaskListModel
from app.repositories.task_list_repository import TaskListRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task_list import TaskListCreate, TaskListUpdate
from app.services.exceptions import TaskListNotFoundError


class TaskListService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = TaskListRepository(session)
        self._task_repository = TaskRepository(session)

    async def create_task_list(self, data: TaskListCreate, owner_id: int) -> TaskListModel:
        task_list = TaskListModel(name=data.name, description=data.description, owner_id=owner_id)
        task_list = await self._repository.add(task_list)
        await self._session.commit()
        return task_list

    async def get_task_list(self, list_id: int) -> TaskListModel:
        task_list = await self._repository.get_by_id(list_id)
        if task_list is None:
            raise TaskListNotFoundError(list_id)
        return task_list

    async def list_task_lists(self, *, offset: int = 0, limit: int = 100) -> list[TaskListModel]:
        return await self._repository.list_all(offset=offset, limit=limit)

    async def update_task_list(self, list_id: int, data: TaskListUpdate) -> TaskListModel:
        task_list = await self.get_task_list(list_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task_list, field, value)
        await self._session.commit()
        await self._session.refresh(task_list)
        return task_list

    async def delete_task_list(self, list_id: int) -> None:
        task_list = await self.get_task_list(list_id)
        await self._repository.delete(task_list)
        await self._session.commit()

    async def list_tasks(
        self,
        list_id: int,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[TaskModel], float]:
        await self.get_task_list(list_id)

        tasks = await self._task_repository.list_by_list_id(
            list_id, status=status, priority=priority, offset=offset, limit=limit
        )
        total, completed = await self._task_repository.count_all_and_completed(list_id)
        completion_percentage = round((completed / total * 100), 1) if total else 0.0

        return tasks, completion_percentage
