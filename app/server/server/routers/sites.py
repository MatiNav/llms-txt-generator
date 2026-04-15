from fastapi import APIRouter, Depends, Query

from server.dependencies import get_run_service
from server.schemas.sites import SiteResponse
from server.services.run_service import RunService


router = APIRouter(prefix="/api", tags=["sites"])


@router.get("/sites", response_model=list[SiteResponse])
async def list_sites(
    query: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=20, ge=1, le=100),
    run_service: RunService = Depends(get_run_service),
) -> list[SiteResponse]:
    return await run_service.list_sites(query_text=query, limit=limit)
