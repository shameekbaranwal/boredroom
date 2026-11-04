"""agenda position: your own order for the games on your agenda

Revision ID: a3d6b8e2f159
Revises: c2f7a9d14e83
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3d6b8e2f159'
down_revision: Union[str, Sequence[str], None] = 'c2f7a9d14e83'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agenda", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("agenda", "position")
