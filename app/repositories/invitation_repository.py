from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import InvitationModel


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: InvitationModel) -> InvitationModel:
        self._session.add(invitation)
        await self._session.flush()
        return invitation
