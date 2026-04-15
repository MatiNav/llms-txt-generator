from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse

from server.dependencies import get_run_events_service
from server.services.run_events_service import RunEventsService


router = APIRouter(prefix="/api", tags=["run-events"])


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: UUID,
    run_events_service: RunEventsService = Depends(get_run_events_service),
) -> EventSourceResponse:
    run_exists = await run_events_service.run_exists(run_id=run_id)
    if not run_exists:
        raise HTTPException(status_code=404, detail="Run not found")

    return EventSourceResponse(
        run_events_service.stream_run_events(run_id=run_id),
        ping=15,
        media_type="text/event-stream",
    )
