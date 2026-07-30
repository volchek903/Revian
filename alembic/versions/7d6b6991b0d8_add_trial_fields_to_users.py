"""add trial fields to users

Revision ID: 7d6b6991b0d8
Revises: cce6ef376abe
Create Date: 2026-07-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d6b6991b0d8"
down_revision: Union[str, Sequence[str], None] = "cce6ef376abe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("referral_status", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("referred_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("trial_ends_at")
        batch_op.drop_column("referred_at")
        batch_op.drop_column("referral_status")
