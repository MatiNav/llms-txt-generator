from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from server.dependencies import get_run_service
from server.schemas.runs import RunStatusResponse
from server.services.run_service import RunService


router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(
    run_id: UUID,
    run_service: RunService = Depends(get_run_service),
) -> RunStatusResponse:
    run_status = await run_service.get_run_status(run_id=run_id)
    if run_status is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_status
