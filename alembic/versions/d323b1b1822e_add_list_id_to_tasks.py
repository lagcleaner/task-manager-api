"""add list_id to tasks

Revision ID: d323b1b1822e
Revises: 331a4f5b5286
Create Date: 2026-09-18 23:23:34.764358

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d323b1b1822e"
down_revision: str | None = "331a4f5b5286"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("list_id", sa.Integer(), nullable=False))
    op.create_foreign_key("fk_tasks_list_id_task_lists", "tasks", "task_lists", ["list_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tasks_list_id_task_lists", "tasks", type_="foreignkey")
    op.drop_column("tasks", "list_id")
