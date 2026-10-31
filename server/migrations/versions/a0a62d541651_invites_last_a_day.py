"""invites last a day

Revision ID: a0a62d541651
Revises: b0940d9c51ef
Create Date: 2026-10-31 06:13:11.937963

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0a62d541651'
down_revision: Union[str, Sequence[str], None] = 'b0940d9c51ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Invites now last a day. The ones already handed out get a day from now, so a link
    sitting in a group chat keeps working until tomorrow and then stops."""
    op.execute("UPDATE invite SET expires_at = now() + interval '24 hours' "
               "WHERE expires_at IS NULL AND revoked_at IS NULL")


def downgrade() -> None:
    """Nothing to undo: the expiry dates stay, and are harmless."""
