"""reset clock: show resets as a clock time instead of time left

Revision ID: c2f7a9d14e83
Revises: d4e8f2a61c35
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c2f7a9d14e83'
down_revision: Union[str, Sequence[str], None] = 'd4e8f2a61c35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("person", sa.Column("reset_clock", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("person", "reset_clock")
