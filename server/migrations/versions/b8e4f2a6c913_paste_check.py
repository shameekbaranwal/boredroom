"""shortcut: a filing-only key for the phone shortcut, and filing a paste at once

Revision ID: b8e4f2a6c913
Revises: e7c1d5a9b302
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8e4f2a6c913'
down_revision: Union[str, Sequence[str], None] = 'e7c1d5a9b302'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_token", sa.Column("scope", sa.String(12), nullable=True))
    op.add_column("person", sa.Column("paste_check", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("person", "paste_check")
    op.drop_column("auth_token", "scope")
