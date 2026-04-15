"""add ctx artifact keys to runs

Revision ID: 7b6c5d4e3f21
Revises: e4b1d0b9a7d2
Create Date: 2026-04-15 16:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b6c5d4e3f21"
down_revision: Union[str, Sequence[str], None] = "e4b1d0b9a7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("runs", sa.Column("llms_ctx_s3_key", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("llms_ctx_full_s3_key", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runs", "llms_ctx_full_s3_key")
    op.drop_column("runs", "llms_ctx_s3_key")
