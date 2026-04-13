import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    SmallInteger,
    Integer,
    ForeignKey,
    Index,
    CheckConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class RunPage(Base):
    __tablename__ = "run_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    normalized_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    depth: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    fetch_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="queued",
    )

    # Refresher change detection priority: etag > content_hash > last_modified
    page_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="NEW",
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    etag: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_modified: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    html_s3_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    fetched_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now,
    )

    run: Mapped["Run"] = relationship(back_populates="pages", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "depth >= 0",
            name="valid_depth",
        ),
        CheckConstraint(
            "fetch_status IN ('queued', 'fetched', 'failed')",
            name="valid_fetch_status",
        ),
        CheckConstraint(
            "page_status IN ('UNCHANGED', 'CHANGED', 'NEW', 'REMOVED', 'FAILED')",
            name="valid_page_status",
        ),
        UniqueConstraint("run_id", "normalized_url", name="uq_run_page_url"),
        Index("idx_run_pages_run", "run_id"),
        Index("idx_run_pages_status", "run_id", "fetch_status", "page_status"),
    )
