"""remove run artifact key columns

Revision ID: 8c9d0e1f2a34
Revises: 7b6c5d4e3f21
Create Date: 2026-04-15 18:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c9d0e1f2a34"
down_revision: Union[str, Sequence[str], None] = "7b6c5d4e3f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("runs", "bundle_s3_key")
    op.drop_column("runs", "llms_ctx_full_s3_key")
    op.drop_column("runs", "llms_ctx_s3_key")
    op.drop_column("runs", "llms_txt_s3_key")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("runs", sa.Column("llms_txt_s3_key", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("llms_ctx_s3_key", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("llms_ctx_full_s3_key", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("bundle_s3_key", sa.String(), nullable=True))
