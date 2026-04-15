from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from server.dependencies import get_download_service
from server.errors.run import RunNotCompletedError
from server.schemas.downloads import RunDownloadsResponse
from server.services.download_service import DownloadService


router = APIRouter(prefix="/api", tags=["downloads"])


@router.get("/runs/{run_id}/downloads", response_model=RunDownloadsResponse)
async def get_run_downloads(
    run_id: UUID,
    download_service: DownloadService = Depends(get_download_service),
) -> RunDownloadsResponse:
    try:
        run_download_links = await download_service.get_run_download_links(
            run_id=run_id
        )
    except RunNotCompletedError as run_not_completed_error:
        raise HTTPException(
            status_code=409,
            detail=run_not_completed_error.to_response_detail(),
        ) from run_not_completed_error

    if run_download_links is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_download_links
