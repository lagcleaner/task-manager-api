from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.invitation import InvitationModel
    from app.models.task import TaskModel


class TaskListModel(Base):
    __tablename__ = "task_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(default=None)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="task_list", cascade="all, delete-orphan", lazy="selectin"
    )
    invitations: Mapped[list["InvitationModel"]] = relationship(
        back_populates="task_list", cascade="all, delete-orphan", lazy="selectin"
    )
