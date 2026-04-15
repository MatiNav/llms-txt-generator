"""add ready_for_llm_generation run state

Revision ID: e4b1d0b9a7d2
Revises: 9af7f3f4c1b2
Create Date: 2026-04-15 10:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4b1d0b9a7d2"
down_revision: Union[str, Sequence[str], None] = "9af7f3f4c1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS ck_runs_valid_state")
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS valid_state")
    op.create_check_constraint(
        "ck_runs_valid_state",
        "runs",
        "state IN ('discovering', 'processing', 'ready_for_llm_generation', 'completed', 'failed')",
    )

    op.drop_index("uq_runs_site_inflight", table_name="runs")
    op.create_index(
        "uq_runs_site_inflight",
        "runs",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text(
            "state IN ('discovering', 'processing', 'ready_for_llm_generation')"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_runs_site_inflight", table_name="runs")
    op.create_index(
        "uq_runs_site_inflight",
        "runs",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('discovering', 'processing')"),
    )

    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS ck_runs_valid_state")
    op.execute("ALTER TABLE runs DROP CONSTRAINT IF EXISTS valid_state")
    op.create_check_constraint(
        "ck_runs_valid_state",
        "runs",
        "state IN ('discovering', 'processing', 'completed', 'failed')",
    )
