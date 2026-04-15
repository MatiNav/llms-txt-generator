import logging
from uuid import UUID

from server.repositories.run_repository import RunRepository, RunStatusSnapshot
from server.schemas.runs import RunStatusResponse
from server.schemas.sites import SiteResponse
from shared.constants.page_status import (
    FETCH_STATUS_FAILED,
    FETCH_STATUS_FETCHED,
    FETCH_STATUS_FETCH_IN_PROGRESS,
    PAGE_STATUS_UNCHANGED,
)
from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_DISCOVERING,
    RUN_STATE_FAILED,
    RUN_STATE_PROCESSING,
    RUN_STATE_READY_FOR_LLM_GENERATION,
)
from shared.logging import log_event


logger = logging.getLogger(__name__)


class RunService:
    def __init__(self, run_repository: RunRepository) -> None:
        self.run_repository = run_repository

    async def run_exists(self, run_id: UUID) -> bool:
        return await self.run_repository.run_exists(run_id)

    async def get_run_snapshot(self, run_id: UUID) -> RunStatusSnapshot | None:
        return await self.run_repository.get_run_snapshot(run_id=run_id)

    async def get_root_render_mode(self, run_id: UUID) -> str | None:
        return await self.run_repository.get_root_render_mode(run_id=run_id)

    async def find_latest_completed_source_run_id(
        self,
        *,
        site_id: UUID,
        render_mode: str,
    ) -> UUID | None:
        return await self.run_repository.find_latest_completed_source_run_id(
            site_id=site_id,
            render_mode=render_mode,
        )

    async def get_run_status(self, run_id: UUID) -> RunStatusResponse | None:
        snapshot = await self.get_run_snapshot(run_id=run_id)
        if snapshot is None:
            return None

        stage_name = self._map_stage(snapshot)
        completed_reason = self._derive_completed_reason(snapshot)
        return RunStatusResponse(
            run_id=snapshot.run_id,
            site_id=snapshot.site_id,
            site_root_url=snapshot.site_root_url,
            state=snapshot.run_state,
            stage=stage_name,
            pages_detected=snapshot.pages_detected,
            pages_queued=snapshot.pages_queued,
            pages_completed=snapshot.pages_completed,
            completed_reason=completed_reason,
            error_message=snapshot.error_message,
            updated_at=snapshot.updated_at,
        )

    async def list_sites(
        self, query_text: str | None, limit: int
    ) -> list[SiteResponse]:
        site_snapshots = await self.run_repository.list_sites(
            query_text=query_text,
            limit=limit,
        )
        return [
            SiteResponse(
                site_id=site_snapshot.site_id,
                root_url=site_snapshot.root_url,
                created_at=site_snapshot.created_at,
            )
            for site_snapshot in site_snapshots
        ]

    def _map_stage(self, snapshot: RunStatusSnapshot) -> str:
        if snapshot.run_state == RUN_STATE_DISCOVERING:
            if snapshot.root_fetch_status in {
                FETCH_STATUS_FETCH_IN_PROGRESS,
                FETCH_STATUS_FETCHED,
                FETCH_STATUS_FAILED,
            }:
                return "fetching"
            return "discovering"

        if snapshot.run_state == RUN_STATE_PROCESSING:
            return "processing"

        if snapshot.run_state == RUN_STATE_READY_FOR_LLM_GENERATION:
            return "llm_generation"

        if snapshot.run_state == RUN_STATE_COMPLETED:
            return "completed"

        if snapshot.run_state == RUN_STATE_FAILED:
            return "failed"

        log_event(
            logger,
            logging.WARNING,
            "run.stage.unknown_state",
            service="server",
            component="run_service",
            run_id=str(snapshot.run_id),
            state=snapshot.run_state,
        )
        return "unknown"

    def _derive_completed_reason(self, snapshot: RunStatusSnapshot) -> str | None:
        if snapshot.run_state != RUN_STATE_COMPLETED:
            return None

        if snapshot.root_page_status == PAGE_STATUS_UNCHANGED:
            return "unchanged_root"

        return "processed"
