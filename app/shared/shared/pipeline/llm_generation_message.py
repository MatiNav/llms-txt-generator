from typing import Any, TypedDict


class LlmGenerationRequestedMessage(TypedDict):
    run_id: str
    site_id: str


def build_llm_generation_requested_message(
    *,
    run_id: str,
    site_id: str,
) -> LlmGenerationRequestedMessage:
    return {
        "run_id": str(run_id),
        "site_id": str(site_id),
    }


def parse_llm_generation_requested_message(
    raw_payload: dict[str, Any],
) -> LlmGenerationRequestedMessage:
    return {
        "run_id": str(raw_payload["run_id"]),
        "site_id": str(raw_payload["site_id"]),
    }
