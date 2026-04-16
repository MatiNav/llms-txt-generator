import asyncio
import logging
from typing import Any

from handlers.ecs_tasks.spa_fetcher.runtime import (
    SpaFetcherRuntime,
    build_spa_fetcher_runtime,
)
from shared.constants.render_mode import RENDER_MODE_SPA
from shared.logging import configure_json_logging, log_event
from shared.pipeline.fetch_message import parse_fetch_requested_message
from shared.pipeline.json_payload import parse_json_object_payload


logger = logging.getLogger(__name__)


async def process_raw_message(
    raw_message: dict[str, Any], runtime: SpaFetcherRuntime
) -> None:
    receipt_handle = raw_message.get("ReceiptHandle")
    raw_body = str(raw_message.get("Body", "{}"))

    parsed_payload = parse_json_object_payload(raw_body)

    fetch_message = parse_fetch_requested_message(parsed_payload)
    if fetch_message["render_mode"] != RENDER_MODE_SPA:
        raise ValueError("SPA fetcher received non-spa render_mode message")

    log_event(
        logger,
        logging.INFO,
        "spa_fetcher.message.received",
        run_id=fetch_message["run_id"],
        page_id=fetch_message["page_id"],
        site_id=fetch_message["site_id"],
        page_url=fetch_message["url"],
        page_depth=fetch_message["depth"],
        receipt_handle_present=bool(receipt_handle),
    )

    try:
        await runtime.fetcher_core.process(
            fetch_message=fetch_message,
            fetcher_adapter=runtime.fetcher_adapter,
        )
    except Exception as message_error:
        log_event(
            logger,
            logging.ERROR,
            "spa_fetcher.message.failed",
            run_id=fetch_message["run_id"],
            page_id=fetch_message["page_id"],
            site_id=fetch_message["site_id"],
            page_url=fetch_message["url"],
            page_depth=fetch_message["depth"],
            error_type=type(message_error).__name__,
            error_message=str(message_error)[:500],
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "spa_fetcher.message.completed",
        run_id=fetch_message["run_id"],
        page_id=fetch_message["page_id"],
        site_id=fetch_message["site_id"],
        page_url=fetch_message["url"],
        page_depth=fetch_message["depth"],
    )

    if receipt_handle:
        await runtime.queue_client.delete_message(receipt_handle=receipt_handle)


async def main_async() -> None:
    configure_json_logging()
    runtime = build_spa_fetcher_runtime()
    try:
        while True:
            raw_messages = await runtime.queue_client.receive_messages(
                max_messages=10,
                wait_time_seconds=20,
            )
            if not raw_messages:
                continue

            log_event(
                logger,
                logging.INFO,
                "spa_fetcher.batch.received",
                batch_size=len(raw_messages),
            )

            # The runtime currently holds a shared SQLAlchemy AsyncSession.
            # Processing messages concurrently causes session state conflicts.
            for message in raw_messages:
                await process_raw_message(message, runtime)
    except Exception as runtime_error:
        log_event(
            logger,
            logging.ERROR,
            "spa_fetcher.runtime.failed",
            service="spa_fetcher",
            error_type=type(runtime_error).__name__,
            error_message=str(runtime_error)[:500],
        )
        raise
    finally:
        await runtime.fetcher_core.repository.database_session.close()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
