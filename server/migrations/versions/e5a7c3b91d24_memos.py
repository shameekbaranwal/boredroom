"""memos from the chair

Revision ID: e5a7c3b91d24
Revises: c3d1e7a90b12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e5a7c3b91d24'
down_revision: Union[str, Sequence[str], None] = 'c3d1e7a90b12'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board_id", sa.Integer(), sa.ForeignKey("board.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("subjects", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("game_id", sa.String(40)),
        sa.Column("result_id", sa.Integer(), sa.ForeignKey("result.id", ondelete="CASCADE")),
        sa.Column("facts", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("interest", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("board_id", "key"),
    )
    op.create_index("ix_memo_board_id", "memo", ["board_id"])
    op.create_index("ix_memo_day", "memo", ["day"])
    op.create_table(
        "memo_dismissal",
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("memo_id", sa.Integer(), sa.ForeignKey("memo.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("memo_dismissal")
    op.drop_index("ix_memo_day", "memo")
    op.drop_index("ix_memo_board_id", "memo")
    op.drop_table("memo")
