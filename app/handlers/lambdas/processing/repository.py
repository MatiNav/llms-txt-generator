from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.constants.page_status import (
    FETCH_STATUS_FETCHED,
    FETCH_STATUS_QUEUED,
    PAGE_STATUS_FAILED,
)
from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_FAILED,
    RUN_STATE_PROCESSING,
    RUN_STATE_READY_FOR_LLM_GENERATION,
)
from shared.models import Run, RunPage
from shared.pipeline.processing_types import PageForProcessing


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    site_id: str
    state: str


class ProcessingRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def get_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        snapshot_statement = (
            select(Run.id, Run.site_id, Run.state).where(Run.id == run_id).limit(1)
        )
        snapshot_result = await self.database_session.execute(snapshot_statement)
        snapshot_row = snapshot_result.first()
        if snapshot_row is None:
            return None

        return RunSnapshot(
            run_id=str(snapshot_row[0]),
            site_id=str(snapshot_row[1]),
            state=str(snapshot_row[2]),
        )

    async def queued_pages_count(self, run_id: str) -> int:
        queued_count_statement = (
            select(func.count())
            .select_from(RunPage)
            .where(
                RunPage.run_id == run_id,
                RunPage.fetch_status == FETCH_STATUS_QUEUED,
            )
        )
        queued_count_result = await self.database_session.execute(
            queued_count_statement
        )
        return int(queued_count_result.scalar_one())

    async def list_fetched_pages_for_processing(
        self, run_id: str
    ) -> list[PageForProcessing]:
        pages_statement = (
            select(
                RunPage.id,
                RunPage.url,
                RunPage.normalized_url,
                RunPage.depth,
                RunPage.html_s3_key,
            )
            .where(RunPage.run_id == run_id)
            .where(RunPage.fetch_status == FETCH_STATUS_FETCHED)
            .where(RunPage.html_s3_key.is_not(None))
            .order_by(RunPage.depth.asc(), RunPage.normalized_url.asc())
        )
        pages_result = await self.database_session.execute(pages_statement)

        pages_for_processing: list[PageForProcessing] = []
        for page_row in pages_result.all():
            pages_for_processing.append(
                PageForProcessing(
                    run_page_id=str(page_row[0]),
                    url=str(page_row[1]),
                    normalized_url=str(page_row[2]),
                    depth=int(page_row[3]),
                    html_s3_key=str(page_row[4]),
                )
            )
        return pages_for_processing

    async def update_page_metadata(
        self,
        *,
        run_page_id: str,
        metadata_json: dict,
    ) -> None:
        update_statement = (
            update(RunPage)
            .where(RunPage.id == run_page_id)
            .values(metadata_json=metadata_json)
        )
        await self.database_session.execute(update_statement)

    async def mark_page_failed_for_processing(
        self,
        *,
        run_page_id: str,
        error_message: str,
    ) -> None:
        current_metadata = await self._current_metadata_for_page(run_page_id)
        next_metadata = {
            **current_metadata,
            "processing_error": error_message[:1000],
        }

        failed_statement = (
            update(RunPage)
            .where(RunPage.id == run_page_id)
            .values(
                page_status=PAGE_STATUS_FAILED,
                metadata_json=next_metadata,
            )
        )
        await self.database_session.execute(failed_statement)

    async def mark_run_failed(self, *, run_id: str, error_message: str) -> bool:
        failed_statement = (
            update(Run)
            .where(Run.id == run_id)
            .where(Run.state == RUN_STATE_PROCESSING)
            .values(
                state=RUN_STATE_FAILED,
                error_message=error_message[:1000],
                completed_at=func.now(),
            )
            .returning(Run.id)
        )
        failed_result = await self.database_session.execute(failed_statement)
        return failed_result.first() is not None

    async def mark_run_ready_for_llm_generation(
        self,
        *,
        run_id: str,
        output_mode: str,
        root_key: str,
        bundle_key: str | None,
    ) -> bool:
        is_hierarchical = output_mode == "hierarchical"
        ready_statement = (
            update(Run)
            .where(Run.id == run_id)
            .where(Run.state == RUN_STATE_PROCESSING)
            .values(
                state=RUN_STATE_READY_FOR_LLM_GENERATION,
                llms_txt_s3_key=(None if is_hierarchical else root_key),
                bundle_s3_key=(bundle_key if is_hierarchical else None),
                error_message=None,
            )
            .returning(Run.id)
        )
        ready_result = await self.database_session.execute(ready_statement)
        return ready_result.first() is not None

    @staticmethod
    def is_terminal_state(run_state: str) -> bool:
        return run_state in {RUN_STATE_COMPLETED, RUN_STATE_FAILED}

    async def _current_metadata_for_page(self, run_page_id: str) -> dict:
        metadata_statement = (
            select(RunPage.metadata_json).where(RunPage.id == run_page_id).limit(1)
        )
        metadata_result = await self.database_session.execute(metadata_statement)
        metadata_value = metadata_result.scalar_one_or_none()
        if isinstance(metadata_value, dict):
            return metadata_value
        return {}
