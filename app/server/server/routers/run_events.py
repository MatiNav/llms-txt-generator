import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette import EventSourceResponse

from server.dependencies import get_run_events_service
from server.services.run_events_service import RunEventsService
from shared.logging import log_event


router = APIRouter(prefix="/api", tags=["run-events"])
logger = logging.getLogger(__name__)


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: UUID,
    run_events_service: RunEventsService = Depends(get_run_events_service),
) -> EventSourceResponse:
    log_event(
        logger,
        logging.INFO,
        "api.run_events.request_received",
        service="server",
        component="run_events_router",
        run_id=str(run_id),
    )

    run_exists = await run_events_service.run_exists(run_id=run_id)
    if not run_exists:
        log_event(
            logger,
            logging.WARNING,
            "api.run_events.run_not_found",
            service="server",
            component="run_events_router",
            run_id=str(run_id),
        )
        raise HTTPException(status_code=404, detail="Run not found")

    log_event(
        logger,
        logging.INFO,
        "api.run_events.stream_opened",
        service="server",
        component="run_events_router",
        run_id=str(run_id),
    )

    return EventSourceResponse(
        run_events_service.stream_run_events(run_id=run_id),
        ping=15,
        media_type="text/event-stream",
    )
