from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import InvitationModel


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: InvitationModel) -> InvitationModel:
        self._session.add(invitation)
        await self._session.flush()
        return invitation

    async def exists_for_list_and_email(self, list_id: int, email: str) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(InvitationModel)
            .where(InvitationModel.list_id == list_id, InvitationModel.email == email)
        )
        return result.scalar_one() > 0

    async def list_by_list_id(
        self, list_id: int, *, offset: int = 0, limit: int = 100
    ) -> list[InvitationModel]:
        result = await self._session.execute(
            select(InvitationModel)
            .where(InvitationModel.list_id == list_id)
            .order_by(InvitationModel.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
