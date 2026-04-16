from typing import Any

from shared.pipeline.run_site_message import (
    RunSiteMessage,
    build_run_site_message,
    parse_run_site_message,
)


LlmGenerationRequestedMessage = RunSiteMessage


def build_llm_generation_requested_message(
    *,
    run_id: str,
    site_id: str,
) -> LlmGenerationRequestedMessage:
    return build_run_site_message(run_id=run_id, site_id=site_id)


def parse_llm_generation_requested_message(
    raw_payload: dict[str, Any],
) -> LlmGenerationRequestedMessage:
    return parse_run_site_message(raw_payload)
