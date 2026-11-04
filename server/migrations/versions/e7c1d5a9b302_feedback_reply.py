"""feedback reply: the developer's answer to a note, shown to its sender

Revision ID: e7c1d5a9b302
Revises: a3d6b8e2f159
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7c1d5a9b302'
down_revision: Union[str, Sequence[str], None] = 'a3d6b8e2f159'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feedback", sa.Column("reply", sa.Text(), nullable=True))
    op.add_column("feedback", sa.Column("reply_release", sa.String(20), nullable=True))
    op.add_column("feedback", sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("feedback", sa.Column("reply_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for c in ("reply_read_at", "replied_at", "reply_release", "reply"):
        op.drop_column("feedback", c)
