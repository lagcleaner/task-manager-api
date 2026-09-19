from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserModel


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> UserModel | None:
        return await self._session.get(UserModel, user_id)

    async def get_by_email(self, email: str) -> UserModel | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        return result.scalar_one_or_none()

    async def add(self, user: UserModel) -> UserModel:
        self._session.add(user)
        await self._session.flush()
        return user
