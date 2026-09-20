from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import InvitationModel
from app.models.task_list import TaskListModel
from app.repositories.invitation_repository import InvitationRepository


async def _create_task_list(session: AsyncSession) -> TaskListModel:
    task_list = TaskListModel(name="Groceries", owner_id=1)
    session.add(task_list)
    await session.commit()
    await session.refresh(task_list)
    return task_list


async def _create_invitation(session: AsyncSession, list_id: int, email: str) -> InvitationModel:
    invitation = InvitationModel(list_id=list_id, email=email, invited_by_id=1)
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def test_soft_delete_by_list_id_cascades_to_invitations(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    other_list = await _create_task_list(db_session)
    invitation = await _create_invitation(db_session, task_list.id, "one@example.com")
    other_invitation = await _create_invitation(db_session, other_list.id, "two@example.com")
    repository = InvitationRepository(db_session)

    await repository.soft_delete_by_list_id(task_list.id)

    await db_session.refresh(invitation)
    await db_session.refresh(other_invitation)
    assert invitation.deleted_at is not None
    assert other_invitation.deleted_at is None


async def test_soft_delete_by_list_id_only_touches_active_rows(db_session: AsyncSession) -> None:
    task_list = await _create_task_list(db_session)
    invitation = await _create_invitation(db_session, task_list.id, "one@example.com")
    repository = InvitationRepository(db_session)

    await repository.soft_delete_by_list_id(task_list.id)
    result = await db_session.execute(
        select(InvitationModel).where(InvitationModel.id == invitation.id)
    )
    stored = result.scalar_one()

    assert stored.deleted_at is not None
