from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.run import Run
from shared.models.run_page import RunPage
from shared.models.site import Site


@dataclass(frozen=True)
class RunStatusSnapshot:
    run_id: UUID
    site_id: UUID
    site_root_url: str
    run_state: str
    pages_queued: int
    pages_completed: int
    pages_detected: int
    root_fetch_status: str | None
    error_message: str | None
    updated_at: datetime


@dataclass(frozen=True)
class SiteSnapshot:
    site_id: UUID
    root_url: str
    created_at: datetime


class RunRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def run_exists(self, run_id: UUID) -> bool:
        run_id_statement: Select[tuple[UUID]] = (
            select(Run.id).where(Run.id == run_id).limit(1)
        )
        run_id_result = await self.database_session.execute(run_id_statement)
        return run_id_result.scalar_one_or_none() is not None

    async def get_run_snapshot(self, run_id: UUID) -> RunStatusSnapshot | None:
        detected_count_subquery = (
            select(func.count())
            .select_from(RunPage)
            .where(RunPage.run_id == run_id)
            .scalar_subquery()
        )
        root_fetch_status_subquery = (
            select(RunPage.fetch_status)
            .where(RunPage.run_id == run_id)
            .where(RunPage.depth == 0)
            .order_by(RunPage.updated_at.desc())
            .limit(1)
            .scalar_subquery()
        )

        snapshot_statement = (
            select(
                Run.id,
                Run.site_id,
                Site.root_url,
                Run.state,
                Run.pages_queued,
                Run.pages_completed,
                detected_count_subquery,
                root_fetch_status_subquery,
                Run.error_message,
                Run.updated_at,
            )
            .outerjoin(Site, Site.id == Run.site_id)
            .where(Run.id == run_id)
            .limit(1)
        )
        snapshot_row = (await self.database_session.execute(snapshot_statement)).first()
        if snapshot_row is None:
            return None

        site_root_url = snapshot_row[2]
        if site_root_url is None:
            raise RuntimeError("Run exists but site record is missing")

        return RunStatusSnapshot(
            run_id=snapshot_row[0],
            site_id=snapshot_row[1],
            site_root_url=site_root_url,
            run_state=snapshot_row[3],
            pages_queued=snapshot_row[4],
            pages_completed=snapshot_row[5],
            pages_detected=snapshot_row[6],
            root_fetch_status=snapshot_row[7],
            error_message=snapshot_row[8],
            updated_at=snapshot_row[9],
        )

    async def list_sites(
        self, query_text: str | None, limit: int
    ) -> list[SiteSnapshot]:
        sites_statement = select(Site.id, Site.root_url, Site.created_at)
        if query_text is not None and query_text.strip() != "":
            like_pattern = f"%{query_text.strip().lower()}%"
            sites_statement = sites_statement.where(
                func.lower(Site.root_url).like(like_pattern)
            )

        sites_statement = sites_statement.order_by(Site.created_at.desc()).limit(limit)
        sites_rows = (await self.database_session.execute(sites_statement)).all()
        return [
            SiteSnapshot(
                site_id=site_row[0], root_url=site_row[1], created_at=site_row[2]
            )
            for site_row in sites_rows
        ]
