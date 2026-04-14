import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from server.dependencies import get_generation_service
from server.schemas.generate import GenerateRequest, GenerateResponse
from server.services.generation_service import GenerationService
from server.utils.url import extract_host_for_logging
from shared.logging import log_event


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    request: Request,
    generation_service: GenerationService = Depends(get_generation_service),
) -> GenerateResponse:
    request_id = getattr(request.state, "request_id", None)
    url_host = extract_host_for_logging(payload.url)

    log_event(
        logger,
        logging.INFO,
        "api.generate.request_received",
        service="server",
        component="generate_router",
        request_id=request_id,
        url_host=url_host,
    )

    try:
        run, coalesced = await generation_service.generate(
            requested_url=payload.url,
            request_id=request_id,
        )
    except (ValueError, RuntimeError) as error:
        is_client_error = isinstance(error, ValueError)
        log_event(
            logger,
            logging.WARNING if is_client_error else logging.ERROR,
            "api.generate.request_failed",
            service="server",
            component="generate_router",
            request_id=request_id,
            url_host=url_host,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        raise HTTPException(
            status_code=400 if is_client_error else 500,
            detail=str(error) if is_client_error else "Failed to generate run",
        ) from error

    response_payload = GenerateResponse(
        run_id=run.id,
        site_id=run.site_id,
        state=run.state,
        coalesced=coalesced,
    )

    log_event(
        logger,
        logging.INFO,
        "api.generate.request_completed",
        service="server",
        component="generate_router",
        request_id=request_id,
        run_id=response_payload.run_id,
        site_id=response_payload.site_id,
        state=response_payload.state,
        coalesced=response_payload.coalesced,
    )

    return response_payload
