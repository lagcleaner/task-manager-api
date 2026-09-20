import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_list import TaskListModel
from app.models.user import UserModel, UserRole
from app.repositories.invitation_repository import InvitationRepository
from app.services.exceptions import DuplicateInvitationError, TaskListNotFoundError
from app.services.notification_service import NotificationService


async def _create_user(session: AsyncSession, email: str) -> UserModel:
    user = UserModel(email=email, hashed_password="not-a-real-hash", role=UserRole.USER)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_task_list(session: AsyncSession, owner_id: int) -> TaskListModel:
    task_list = TaskListModel(name="Groceries", owner_id=owner_id)
    session.add(task_list)
    await session.commit()
    await session.refresh(task_list)
    return task_list


async def test_send_task_list_invitation_persists_invitation(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner@example.com")
    task_list = await _create_task_list(db_session, owner.id)
    service = NotificationService(db_session)

    invitation = await service.send_task_list_invitation(
        task_list.id, "invitee@example.com", invited_by_id=owner.id
    )

    assert invitation.id is not None
    assert invitation.list_id == task_list.id
    assert invitation.email == "invitee@example.com"
    assert invitation.invited_by_id == owner.id


async def test_send_task_list_invitation_raises_when_list_missing(
    db_session: AsyncSession,
) -> None:
    owner = await _create_user(db_session, "owner@example.com")
    service = NotificationService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.send_task_list_invitation(999, "invitee@example.com", invited_by_id=owner.id)


async def test_send_task_list_invitation_raises_when_duplicate(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner2@example.com")
    task_list = await _create_task_list(db_session, owner.id)
    service = NotificationService(db_session)
    await service.send_task_list_invitation(
        task_list.id, "invitee@example.com", invited_by_id=owner.id
    )

    with pytest.raises(DuplicateInvitationError):
        await service.send_task_list_invitation(
            task_list.id, "invitee@example.com", invited_by_id=owner.id
        )


async def test_list_invitations_returns_persisted_invitations(db_session: AsyncSession) -> None:
    owner = await _create_user(db_session, "owner3@example.com")
    task_list = await _create_task_list(db_session, owner.id)
    service = NotificationService(db_session)
    await service.send_task_list_invitation(task_list.id, "one@example.com", invited_by_id=owner.id)
    await service.send_task_list_invitation(task_list.id, "two@example.com", invited_by_id=owner.id)

    invitations = await service.list_invitations(task_list.id)

    assert {invitation.email for invitation in invitations} == {
        "one@example.com",
        "two@example.com",
    }


async def test_list_invitations_raises_when_list_missing(db_session: AsyncSession) -> None:
    service = NotificationService(db_session)

    with pytest.raises(TaskListNotFoundError):
        await service.list_invitations(999)


async def test_send_task_list_invitation_succeeds_after_invitation_soft_deleted(
    db_session: AsyncSession,
) -> None:
    """ADR-018 regression: the duplicate check must only count live invitations, so
    re-inviting the same email/list after the prior invitation row was soft-deleted
    succeeds instead of raising DuplicateInvitationError."""
    owner = await _create_user(db_session, "owner4@example.com")
    task_list = await _create_task_list(db_session, owner.id)
    service = NotificationService(db_session)
    first_invitation = await service.send_task_list_invitation(
        task_list.id, "invitee@example.com", invited_by_id=owner.id
    )

    # Soft-delete the invitation row directly rather than the parent list: today the
    # only real soft-delete path cascades from TaskListService.soft_delete_task_list,
    # which also soft-deletes the list itself and would 404 before reaching the
    # duplicate check. No per-invitation cancel/decline endpoint exists yet, so this
    # isolates what's testable at this layer.
    invitation_repository = InvitationRepository(db_session)
    await invitation_repository.soft_delete_by_list_id(task_list.id)
    await db_session.commit()
    await db_session.refresh(first_invitation)
    assert first_invitation.deleted_at is not None

    second_invitation = await service.send_task_list_invitation(
        task_list.id, "invitee@example.com", invited_by_id=owner.id
    )

    assert second_invitation.id is not None
    assert second_invitation.id != first_invitation.id
    assert second_invitation.deleted_at is None
