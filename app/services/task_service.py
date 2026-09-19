from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel, TaskStatus
from app.repositories.task_list_repository import TaskListRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import TaskListNotFoundError, TaskNotFoundError, UserNotFoundError


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = TaskRepository(session)
        self._task_list_repository = TaskListRepository(session)
        self._user_repository = UserRepository(session)

    async def _ensure_user_exists(self, user_id: int) -> None:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

    async def create_task(self, data: TaskCreate) -> TaskModel:
        task_list = await self._task_list_repository.get_by_id(data.list_id)
        if task_list is None:
            raise TaskListNotFoundError(data.list_id)
        if data.assignee_id is not None:
            await self._ensure_user_exists(data.assignee_id)
        task = TaskModel(
            title=data.title,
            description=data.description,
            list_id=data.list_id,
            priority=data.priority,
            assignee_id=data.assignee_id,
        )
        task = await self._repository.add(task)
        await self._session.commit()
        return task

    async def get_task(self, task_id: int) -> TaskModel:
        task = await self._repository.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def list_tasks(self, *, offset: int = 0, limit: int = 100) -> list[TaskModel]:
        return await self._repository.list_all(offset=offset, limit=limit)

    async def update_task(self, task_id: int, data: TaskUpdate) -> TaskModel:
        task = await self.get_task(task_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("assignee_id") is not None:
            await self._ensure_user_exists(changes["assignee_id"])
        for field, value in changes.items():
            setattr(task, field, value)
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def change_status(self, task_id: int, status: TaskStatus) -> TaskModel:
        task = await self.get_task(task_id)
        task.status = status
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def assign_task(self, task_id: int, assignee_id: int | None) -> TaskModel:
        task = await self.get_task(task_id)
        if assignee_id is not None:
            await self._ensure_user_exists(assignee_id)
        task.assignee_id = assignee_id
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> None:
        task = await self.get_task(task_id)
        await self._repository.delete(task)
        await self._session.commit()
