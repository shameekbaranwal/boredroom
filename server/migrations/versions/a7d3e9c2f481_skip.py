"""skip: a game sat out until it resets

Revision ID: a7d3e9c2f481
Revises: f2c8a4d17e60
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7d3e9c2f481'
down_revision: Union[str, Sequence[str], None] = 'f2c8a4d17e60'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skip",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("game_id", sa.String(40), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skip")
