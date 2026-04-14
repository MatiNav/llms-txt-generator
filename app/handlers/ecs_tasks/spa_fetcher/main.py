import asyncio
import json
import logging
from typing import Any

from handlers.ecs_tasks.spa_fetcher.runtime import (
    SpaFetcherRuntime,
    build_spa_fetcher_runtime,
)
from shared.constants.render_mode import RENDER_MODE_SPA
from shared.logging import configure_json_logging, log_event
from shared.pipeline.fetch_message import parse_fetch_requested_message


logger = logging.getLogger(__name__)


async def process_raw_message(
    raw_message: dict[str, Any], runtime: SpaFetcherRuntime
) -> None:
    receipt_handle = raw_message.get("ReceiptHandle")
    raw_body = str(raw_message.get("Body", "{}"))

    parsed_payload = json.loads(raw_body)
    if not isinstance(parsed_payload, dict):
        raise ValueError("SQS message body must be a JSON object")

    fetch_message = parse_fetch_requested_message(parsed_payload)
    if fetch_message["render_mode"] != RENDER_MODE_SPA:
        raise ValueError("SPA fetcher received non-spa render_mode message")

    await runtime.fetcher_core.process(
        fetch_message=fetch_message,
        fetcher_adapter=runtime.fetcher_adapter,
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

            message_tasks = [
                process_raw_message(message, runtime) for message in raw_messages
            ]
            await asyncio.gather(*message_tasks)
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
