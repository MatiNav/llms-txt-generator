from typing import Any, TypedDict


class ProcessingRequestedMessage(TypedDict):
    run_id: str
    site_id: str


def build_processing_requested_message(
    *,
    run_id: str,
    site_id: str,
) -> ProcessingRequestedMessage:
    return {
        "run_id": str(run_id),
        "site_id": str(site_id),
    }


def parse_processing_requested_message(
    raw_payload: dict[str, Any],
) -> ProcessingRequestedMessage:
    return {
        "run_id": str(raw_payload["run_id"]),
        "site_id": str(raw_payload["site_id"]),
    }
