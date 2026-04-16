"""remove unused site_pages columns

Revision ID: b3f6a1c9d2e4
Revises: 8c9d0e1f2a34
Create Date: 2026-04-15 23:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3f6a1c9d2e4"
down_revision: Union[str, Sequence[str], None] = "8c9d0e1f2a34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("idx_site_pages_active", table_name="site_pages")
    op.drop_column("site_pages", "is_active")
    op.drop_column("site_pages", "last_metadata_json")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "site_pages",
        sa.Column(
            "last_metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "site_pages",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "idx_site_pages_active",
        "site_pages",
        ["site_id", "is_active"],
        unique=False,
    )
    op.alter_column("site_pages", "is_active", server_default=None)
