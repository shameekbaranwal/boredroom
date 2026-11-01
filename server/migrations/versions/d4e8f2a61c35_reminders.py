"""reminders: push subscriptions, the push log, digest and nudge switches

Revision ID: d4e8f2a61c35
Revises: b8e1f4c27d90
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e8f2a61c35'
down_revision: Union[str, Sequence[str], None] = 'b8e1f4c27d90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("membership", sa.Column("digest", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("agenda", sa.Column("nudge", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "push_subscription",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE",
                  name="fk_push_subscription_person_id_person"), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        sa.Column("device", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ok_at", sa.DateTime(timezone=True)),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),
    )
    op.create_index("ix_push_subscription_person_id", "push_subscription", ["person_id"])
    op.create_table(
        "push_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id", ondelete="CASCADE",
                  name="fk_push_log_person_id_person"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("person_id", "key", name="uq_push_log_person_id"),
    )
    op.create_index("ix_push_log_created_at", "push_log", ["created_at"])
    op.create_table(
        "scheduler_state",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("last_tick", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("scheduler_state")
    op.drop_index("ix_push_log_created_at", "push_log")
    op.drop_table("push_log")
    op.drop_index("ix_push_subscription_person_id", "push_subscription")
    op.drop_table("push_subscription")
    op.drop_column("agenda", "nudge")
    op.drop_column("membership", "digest")
