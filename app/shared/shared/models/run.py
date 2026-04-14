import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    SmallInteger,
    Integer,
    ForeignKey,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base
from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_DISCOVERING,
    RUN_STATE_FAILED,
    RUN_STATE_PROCESSING,
)
from shared.constants.run_limits import DEFAULT_MAX_PAGES_PER_RUN
from shared.constants.trigger_reason import (
    TRIGGER_REASON_CRON,
    TRIGGER_REASON_ON_DEMAND,
)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id"),
        nullable=False,
    )
    trigger_reason: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=RUN_STATE_DISCOVERING,
    )
    max_depth: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=2,
    )
    max_pages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_PAGES_PER_RUN,
    )

    # When pages_completed == pages_queued → trigger processing pipeline.
    pages_queued: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    pages_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    llms_txt_s3_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    bundle_s3_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    processing_enqueued_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    site: Mapped["Site"] = relationship(lazy="selectin")
    pages: Mapped[list["RunPage"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            f"trigger_reason IN ('{TRIGGER_REASON_ON_DEMAND}', '{TRIGGER_REASON_CRON}')",
            name="valid_trigger_reason",
        ),
        CheckConstraint(
            f"state IN ('{RUN_STATE_DISCOVERING}', '{RUN_STATE_PROCESSING}', '{RUN_STATE_COMPLETED}', '{RUN_STATE_FAILED}')",
            name="valid_state",
        ),
        # Prevent duplicate in-flight runs for the same site
        Index(
            "uq_runs_site_inflight",
            "site_id",
            unique=True,
            postgresql_where=text(
                f"state IN ('{RUN_STATE_DISCOVERING}', '{RUN_STATE_PROCESSING}')"
            ),
        ),
        Index("idx_runs_site_created", "site_id", "created_at"),
    )
