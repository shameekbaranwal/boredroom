"""agenda sort: how your agenda is ordered, kept with your account

Revision ID: f2c8a4d17e60
Revises: e5a7c3b91d24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f2c8a4d17e60'
down_revision: Union[str, Sequence[str], None] = 'e5a7c3b91d24'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("person", sa.Column("agenda_sort", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("person", "agenda_sort")
