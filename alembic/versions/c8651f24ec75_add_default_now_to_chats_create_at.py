"""add default now() to chats.create_at

Revision ID: c8651f24ec75
Revises: b162c9accbae
Create Date: 2025-07-28 23:09:15.454637

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8651f24ec75"
down_revision: Union[str, Sequence[str], None] = "b162c9accbae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server default now() to chats.create_at."""
    op.alter_column(
        "chats",
        "create_at",
        server_default=sa.func.now(),  # ← ключевая строка
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Remove server default from chats.create_at."""
    op.alter_column(
        "chats",
        "create_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
