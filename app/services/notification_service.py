import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import InvitationModel
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.task_list_repository import TaskListRepository
from app.services.exceptions import TaskListNotFoundError

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = InvitationRepository(session)
        self._task_list_repository = TaskListRepository(session)

    async def send_task_list_invitation(
        self, list_id: int, email: str, invited_by_id: int
    ) -> InvitationModel:
        task_list = await self._task_list_repository.get_by_id(list_id)
        if task_list is None:
            raise TaskListNotFoundError(list_id)

        invitation = InvitationModel(list_id=list_id, email=email, invited_by_id=invited_by_id)
        invitation = await self._repository.add(invitation)
        await self._session.commit()
        await self._session.refresh(invitation)

        # No real SMTP integration: this is the "fake notification" bonus use case,
        # simulated by logging instead of actually sending an email.
        logger.info("[FAKE EMAIL] Invitation sent to %s for task list %s", email, list_id)

        return invitation
