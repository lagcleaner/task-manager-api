"""add invitations table

Revision ID: c32bc182cde9
Revises: 45506c03bca6
Create Date: 2026-09-19 00:15:01.138535

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c32bc182cde9"
down_revision: str | None = "45506c03bca6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["task_lists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("invitations")
