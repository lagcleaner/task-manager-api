from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TaskModel, TaskPriority, TaskStatus
from app.models.task_list import TaskListModel
from app.models.user import UserModel
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.task_list_repository import TaskListRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task_list import TaskListCreate, TaskListUpdate
from app.services.exceptions import NotOwnerError, TaskListNotFoundError


class TaskListService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = TaskListRepository(session)
        self._task_repository = TaskRepository(session)
        self._invitation_repository = InvitationRepository(session)

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

    async def list_deleted_task_lists(
        self, *, offset: int = 0, limit: int = 100
    ) -> list[TaskListModel]:
        return await self._repository.list_deleted(offset=offset, limit=limit)

    async def update_task_list(self, list_id: int, data: TaskListUpdate) -> TaskListModel:
        task_list = await self.get_task_list(list_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task_list, field, value)
        await self._session.commit()
        await self._session.refresh(task_list)
        return task_list

    async def soft_delete_task_list(self, list_id: int, current_user: UserModel) -> None:
        # Lock the parent row before cascading: closes the race where a task/invitation is
        # inserted for this list_id between the parent's soft_delete and the cascade UPDATEs
        # committing. create_task/send_task_list_invitation take the same lock on their read,
        # so they either see the pre-delete row and finish first, or block until this
        # transaction commits and then correctly see the list as deleted.
        task_list = await self._repository.get_by_id(list_id, for_update=True)
        if task_list is None:
            raise TaskListNotFoundError(list_id)
        if task_list.owner_id != current_user.id:
            raise NotOwnerError("task_list", list_id, current_user.id)
        await self._repository.soft_delete(task_list)
        # Cascade: mirror the hard-delete's cascade="all, delete-orphan" semantics.
        await self._task_repository.soft_delete_by_list_id(list_id)
        await self._invitation_repository.soft_delete_by_list_id(list_id)
        await self._session.commit()

    async def permanent_delete_task_list(self, list_id: int) -> None:
        # Bypasses the deleted_at IS NULL default filter: admin can hard-delete an
        # active or already soft-deleted list. Real SQL DELETE cascades to tasks and
        # invitations via cascade="all, delete-orphan" on TaskListModel's relationships.
        task_list = await self._repository.get_by_id_any(list_id)
        if task_list is None:
            raise TaskListNotFoundError(list_id)
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
