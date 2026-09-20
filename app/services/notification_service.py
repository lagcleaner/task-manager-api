import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import InvitationModel
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.task_list_repository import TaskListRepository
from app.services.exceptions import DuplicateInvitationError, TaskListNotFoundError

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = InvitationRepository(session)
        self._task_list_repository = TaskListRepository(session)

    async def send_task_list_invitation(
        self, list_id: int, email: str, invited_by_id: int
    ) -> InvitationModel:
        # Locked read: serializes against TaskListService.soft_delete_task_list's cascade,
        # same reasoning as TaskService.create_task.
        task_list = await self._task_list_repository.get_by_id(list_id, for_update=True)
        if task_list is None:
            raise TaskListNotFoundError(list_id)

        if await self._repository.exists_for_list_and_email(list_id, email):
            raise DuplicateInvitationError(list_id, email)

        invitation = InvitationModel(list_id=list_id, email=email, invited_by_id=invited_by_id)
        invitation = await self._repository.add(invitation)
        await self._session.commit()
        await self._session.refresh(invitation)

        # No real SMTP integration: this is the "fake notification" bonus use case,
        # simulated by logging instead of actually sending an email.
        logger.info("[FAKE EMAIL] Invitation sent to %s for task list %s", email, list_id)

        return invitation

    async def list_invitations(
        self, list_id: int, *, offset: int = 0, limit: int = 100
    ) -> list[InvitationModel]:
        task_list = await self._task_list_repository.get_by_id(list_id)
        if task_list is None:
            raise TaskListNotFoundError(list_id)

        return await self._repository.list_by_list_id(list_id, offset=offset, limit=limit)
