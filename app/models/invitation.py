from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.task_list import TaskListModel
    from app.models.user import UserModel


class InvitationModel(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        Index(
            "uq_invitations_list_id_email_active",
            "list_id",
            "email",
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("task_lists.id"), nullable=False)
    email: Mapped[str] = mapped_column(nullable=False)
    invited_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    task_list: Mapped["TaskListModel"] = relationship(back_populates="invitations", lazy="selectin")
    invited_by: Mapped["UserModel"] = relationship(lazy="selectin")
