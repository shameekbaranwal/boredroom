"""news and feedback: the newest release each person has read, and notes to the developer

Revision ID: b8e1f4c27d90
Revises: a7d3e9c2f481
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b8e1f4c27d90'
down_revision: Union[str, Sequence[str], None] = 'a7d3e9c2f481'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("person", sa.Column("news_seen", sa.String(20), nullable=True))
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("board", sa.String(60), nullable=True),
        sa.Column("release", sa.String(20), nullable=False),
        sa.Column("device", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_person_id", "feedback", ["person_id"])
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_created_at", "feedback")
    op.drop_index("ix_feedback_person_id", "feedback")
    op.drop_table("feedback")
    op.drop_column("person", "news_seen")
