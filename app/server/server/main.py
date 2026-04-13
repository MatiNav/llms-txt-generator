import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from server.config import get_server_settings
from shared.db.migrate import run_migrations
from shared.logging import configure_json_logging, log_event
from server.routers.generate import router as generate_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    configure_json_logging()
    log_event(logger, logging.INFO, "app.startup", service="server", component="main")
    settings = get_server_settings()
    log_event(
        logger,
        logging.INFO,
        "config.validated",
        service="server",
        component="main",
        aws_region=settings.aws_region,
    )
    log_event(
        logger,
        logging.INFO,
        "db.migrations.started",
        service="server",
        component="main",
    )
    await run_migrations()
    log_event(
        logger,
        logging.INFO,
        "db.migrations.completed",
        service="server",
        component="main",
    )

    yield

    log_event(logger, logging.INFO, "app.shutdown", service="server", component="main")


app = FastAPI(title="llms.txt generator server", lifespan=lifespan)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception as request_error:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_event(
            logger,
            logging.ERROR,
            "http.request.failed",
            service="server",
            component="http_middleware",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            error_type=type(request_error).__name__,
            error_message=str(request_error),
        )
        raise

    response.headers["x-request-id"] = request_id
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_event(
        logger,
        logging.INFO,
        "http.request.completed",
        service="server",
        component="http_middleware",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


app.include_router(generate_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
