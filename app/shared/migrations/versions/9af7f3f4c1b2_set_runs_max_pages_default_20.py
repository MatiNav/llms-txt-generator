"""set runs max_pages default to 20

Revision ID: 9af7f3f4c1b2
Revises: 73512bb8daa9
Create Date: 2026-04-14 20:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9af7f3f4c1b2"
down_revision: Union[str, Sequence[str], None] = "73512bb8daa9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "runs",
        "max_pages",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=sa.text("20"),
    )
    op.execute("UPDATE runs SET max_pages = 20")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "runs",
        "max_pages",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=sa.text("200"),
    )
