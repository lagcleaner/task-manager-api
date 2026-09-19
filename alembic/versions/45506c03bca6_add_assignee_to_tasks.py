"""add assignee to tasks

Revision ID: 45506c03bca6
Revises: c3deb8346827
Create Date: 2026-09-18 23:59:11.514415

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "45506c03bca6"
down_revision: str | None = "c3deb8346827"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("assignee_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tasks_assignee_id_users", "tasks", "users", ["assignee_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tasks_assignee_id_users", "tasks", type_="foreignkey")
    op.drop_column("tasks", "assignee_id")
