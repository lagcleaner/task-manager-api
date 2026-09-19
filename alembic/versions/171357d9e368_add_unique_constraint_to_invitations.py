"""add unique constraint to invitations

Revision ID: 171357d9e368
Revises: c32bc182cde9
Create Date: 2026-09-19 00:30:39.544737

"""

from collections.abc import Sequence

from alembic import op

revision: str = "171357d9e368"
down_revision: str | None = "c32bc182cde9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_invitations_list_id_email", "invitations", ["list_id", "email"])


def downgrade() -> None:
    op.drop_constraint("uq_invitations_list_id_email", "invitations", type_="unique")
