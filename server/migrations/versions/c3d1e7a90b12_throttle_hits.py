"""rate limits live in postgres

Revision ID: c3d1e7a90b12
Revises: a0a62d541651
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d1e7a90b12'
down_revision: Union[str, Sequence[str], None] = 'a0a62d541651'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "throttle_hit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_throttle_hit_key_at", "throttle_hit", ["key", "at"])


def downgrade() -> None:
    op.drop_index("ix_throttle_hit_key_at", "throttle_hit")
    op.drop_table("throttle_hit")
