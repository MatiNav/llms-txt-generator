from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.constants.page_status import (
    FETCH_STATUS_FAILED,
    FETCH_STATUS_FETCHED,
    FETCH_STATUS_FETCH_IN_PROGRESS,
    FETCH_STATUS_QUEUED,
    PAGE_STATUS_NEW,
)
from shared.constants.run_state import RUN_STATE_DISCOVERING
from shared.models import Run, RunPage
from shared.pipeline.url_norm import canonical_url


@dataclass(frozen=True)
class ReservedChildPage:
    page_id: str
    url: str


@dataclass(frozen=True)
class RunLimitsSnapshot:
    max_depth: int
    max_pages: int
    pages_queued: int


class FetcherRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def claim_page(self, page_id: str) -> bool:
        claim_statement = (
            update(RunPage)
            .where(RunPage.id == page_id)
            .where(RunPage.fetch_status == FETCH_STATUS_QUEUED)
            .values(
                fetch_status=FETCH_STATUS_FETCH_IN_PROGRESS,
                fetch_started_at=func.now(),
            )
            .returning(RunPage.id)
        )
        claim_result = await self.database_session.execute(claim_statement)
        claimed_row = claim_result.first()
        return claimed_row is not None

    async def get_run_limits(self, run_id: str) -> RunLimitsSnapshot:
        run_limits_statement = (
            select(Run.max_depth, Run.max_pages, Run.pages_queued)
            .where(Run.id == run_id)
            .limit(1)
        )
        run_limits_result = await self.database_session.execute(run_limits_statement)
        max_depth, max_pages, pages_queued = run_limits_result.one()
        return RunLimitsSnapshot(
            max_depth=int(max_depth),
            max_pages=int(max_pages),
            pages_queued=int(pages_queued),
        )

    async def reserve_children(
        self,
        *,
        run_id: str,
        depth: int,
        render_mode: str,
        discovered_urls: list[str],
    ) -> list[ReservedChildPage]:
        reserved_children: list[ReservedChildPage] = []
        for discovered_url in discovered_urls:
            normalized_child_url = canonical_url(discovered_url)

            reserve_statement = (
                postgres_insert(RunPage)
                .values(
                    run_id=run_id,
                    url=discovered_url,
                    normalized_url=normalized_child_url,
                    depth=depth,
                    render_mode=render_mode,
                    fetch_status=FETCH_STATUS_QUEUED,
                    page_status=PAGE_STATUS_NEW,
                )
                .on_conflict_do_nothing(constraint="uq_run_page_url")
                .returning(RunPage.id, RunPage.url)
            )
            reserve_result = await self.database_session.execute(reserve_statement)
            inserted_row = reserve_result.first()
            if inserted_row is None:
                continue

            reserved_children.append(
                ReservedChildPage(
                    page_id=str(inserted_row[0]),
                    url=str(inserted_row[1]),
                )
            )

        if reserved_children:
            await self.database_session.execute(
                update(Run)
                .where(Run.id == run_id)
                .where(Run.state == RUN_STATE_DISCOVERING)
                .values(pages_queued=Run.pages_queued + len(reserved_children))
            )

        return reserved_children

    async def finalize_page_success(
        self,
        *,
        page_id: str,
        html_s3_key: str,
        http_status_code: int | None,
        metadata_json: dict,
    ) -> None:
        await self.database_session.execute(
            update(RunPage)
            .where(RunPage.id == page_id)
            .where(RunPage.fetch_status == FETCH_STATUS_FETCH_IN_PROGRESS)
            .values(
                fetch_status=FETCH_STATUS_FETCHED,
                html_s3_key=html_s3_key,
                http_status=http_status_code,
                metadata_json=metadata_json,
                fetched_at=func.now(),
            )
        )

    async def finalize_page_failure(
        self,
        *,
        page_id: str,
        error_message: str,
    ) -> None:
        await self.database_session.execute(
            update(RunPage)
            .where(RunPage.id == page_id)
            .where(RunPage.fetch_status == FETCH_STATUS_FETCH_IN_PROGRESS)
            .values(
                fetch_status=FETCH_STATUS_FAILED,
                metadata_json={"fetch_error": error_message[:1000]},
                fetched_at=func.now(),
            )
        )

    async def mark_page_completed(self, *, run_id: str) -> None:
        await self.database_session.execute(
            update(Run)
            .where(Run.id == run_id)
            .where(Run.state == RUN_STATE_DISCOVERING)
            .values(pages_completed=Run.pages_completed + 1)
        )

    async def get_run_site_id(self, run_id: str) -> str:
        site_statement = select(Run.site_id).where(Run.id == run_id).limit(1)
        site_result = await self.database_session.execute(site_statement)
        site_id = site_result.scalar_one()
        return str(site_id)
