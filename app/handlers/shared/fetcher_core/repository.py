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
from shared.models import Run, RunPage, SitePage
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


@dataclass(frozen=True)
class SitePageBaseline:
    content_hash: str | None
    etag: str | None
    last_modified: str | None


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

    async def get_site_page_baseline(
        self,
        *,
        site_id: str,
        normalized_url: str,
    ) -> SitePageBaseline | None:
        baseline_statement = (
            select(
                SitePage.last_content_hash,
                SitePage.last_etag,
                SitePage.last_modified,
            )
            .where(SitePage.site_id == site_id)
            .where(SitePage.normalized_url == normalized_url)
            .limit(1)
        )
        baseline_result = await self.database_session.execute(baseline_statement)
        baseline_row = baseline_result.first()
        if baseline_row is None:
            return None

        return SitePageBaseline(
            content_hash=baseline_row[0],
            etag=baseline_row[1],
            last_modified=baseline_row[2],
        )

    async def upsert_site_page_baseline(
        self,
        *,
        site_id: str,
        normalized_url: str,
        run_id: str,
        html_s3_key: str,
        content_hash: str,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        upsert_statement = (
            postgres_insert(SitePage)
            .values(
                site_id=site_id,
                normalized_url=normalized_url,
                last_content_hash=content_hash,
                last_etag=etag,
                last_modified=last_modified,
                last_html_s3_key=html_s3_key,
                last_seen_run_id=run_id,
            )
            .on_conflict_do_update(
                constraint="uq_site_page_url",
                set_={
                    "last_content_hash": content_hash,
                    "last_etag": etag,
                    "last_modified": last_modified,
                    "last_html_s3_key": html_s3_key,
                    "last_seen_run_id": run_id,
                    "updated_at": func.now(),
                },
            )
        )
        await self.database_session.execute(upsert_statement)

    async def finalize_page_success(
        self,
        *,
        page_id: str,
        html_s3_key: str,
        http_status_code: int | None,
        etag: str | None,
        last_modified: str | None,
        content_hash: str,
        page_status: str,
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
                etag=etag,
                last_modified=last_modified,
                content_hash=content_hash,
                page_status=page_status,
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
