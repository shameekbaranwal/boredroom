"""invites

Revision ID: b0940d9c51ef
Revises: 654be387b549
Create Date: 2026-10-31 04:23:19.369059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0940d9c51ef'
down_revision: Union[str, Sequence[str], None] = '654be387b549'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Invites move to their own table. Each board's old random code keeps working
    (as a legacy invite) and each board gets a three-word invite to hand out."""
    import secrets
    from datetime import datetime, timezone
    from boredroom.invites import ADJECTIVES, NOUNS, VERBS

    invite = op.create_table('invite',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('legacy', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['board.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['person.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_invite_board_id'), 'invite', ['board_id'], unique=False)

    conn = op.get_bind()
    boards = conn.execute(sa.text("SELECT id, chair_id, invite_code, created_at FROM board")).all()
    used: set[str] = set()
    rows = []
    for b in boards:
        rows.append({"code": b.invite_code, "board_id": b.id, "created_by": b.chair_id, "legacy": True, "created_at": b.created_at})
        while (code := "-".join(secrets.choice(ws) for ws in (ADJECTIVES, NOUNS, VERBS))) in used:
            pass
        used.add(code)
        rows.append({"code": code, "board_id": b.id, "created_by": b.chair_id, "legacy": False, "created_at": datetime.now(timezone.utc)})
    if rows:
        conn.execute(invite.insert(), rows)
    op.drop_constraint('uq_board_invite_code', 'board', type_='unique')
    op.drop_column('board', 'invite_code')


def downgrade() -> None:
    op.add_column('board', sa.Column('invite_code', sa.String(length=32), nullable=True))
    op.execute("""UPDATE board SET invite_code = (SELECT code FROM invite WHERE invite.board_id = board.id
                  ORDER BY legacy DESC, id LIMIT 1)""")
    op.alter_column('board', 'invite_code', nullable=False)
    op.create_unique_constraint('uq_board_invite_code', 'board', ['invite_code'])
    op.drop_index(op.f('ix_invite_board_id'), table_name='invite')
    op.drop_table('invite')
