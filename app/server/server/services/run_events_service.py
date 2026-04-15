import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

from sse_starlette import ServerSentEvent

from server.repositories.run_repository import RunRepository
from server.services.run_service import RunService
from shared.db.session import get_db_session


class RunEventsService:
    def __init__(self, poll_interval_seconds: float = 1.0) -> None:
        self.poll_interval_seconds = poll_interval_seconds

    async def run_exists(self, run_id: UUID) -> bool:
        async with get_db_session() as database_session:
            run_repository = RunRepository(database_session=database_session)
            run_service = RunService(run_repository=run_repository)
            return await run_service.run_exists(run_id=run_id)

    async def stream_run_events(
        self, run_id: UUID
    ) -> AsyncGenerator[ServerSentEvent, None]:
        event_counter = 1
        last_fingerprint: str | None = None

        connected_payload = {"run_id": str(run_id), "message": "stream_connected"}
        yield ServerSentEvent(
            event="run.connected",
            id=str(event_counter),
            data=json.dumps(connected_payload),
        )
        event_counter += 1

        while True:
            async with get_db_session() as database_session:
                run_repository = RunRepository(database_session=database_session)
                run_service = RunService(run_repository=run_repository)
                run_status = await run_service.get_run_status(run_id=run_id)

            if run_status is None:
                return

            stable_fingerprint_payload = {
                "run_id": str(run_status.run_id),
                "state": run_status.state,
                "stage": run_status.stage,
                "pages_detected": run_status.pages_detected,
                "pages_queued": run_status.pages_queued,
                "pages_completed": run_status.pages_completed,
                "has_llms_txt": run_status.has_llms_txt,
                "has_bundle_zip": run_status.has_bundle_zip,
                "error_message": run_status.error_message,
            }
            current_fingerprint = json.dumps(stable_fingerprint_payload, sort_keys=True)
            if current_fingerprint != last_fingerprint:
                stream_payload = {
                    **run_status.model_dump(mode="json"),
                    "timestamp": run_status.updated_at.isoformat(),
                }
                yield ServerSentEvent(
                    event=self._stage_to_event_name(run_status.stage),
                    id=str(event_counter),
                    data=json.dumps(stream_payload),
                )
                event_counter += 1
                last_fingerprint = current_fingerprint

            if run_status.stage in {"completed", "failed"}:
                return

            await asyncio.sleep(self.poll_interval_seconds)

    def _stage_to_event_name(self, stage_name: str) -> str:
        stage_event_names = {
            "discovering": "run.discovering",
            "fetching": "run.fetch_progress",
            "processing": "run.processing",
            "llm_generation": "run.llm_generation",
            "completed": "run.completed",
            "failed": "run.failed",
        }
        return stage_event_names.get(stage_name, "run.fetch_progress")
