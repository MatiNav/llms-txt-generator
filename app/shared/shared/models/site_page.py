import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class SitePage(Base):
    __tablename__ = "site_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    last_content_hash: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_etag: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_modified: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_html_s3_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    last_seen_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        onupdate=datetime.now,
    )

    __table_args__ = (
        UniqueConstraint("site_id", "normalized_url", name="uq_site_page_url"),
    )
