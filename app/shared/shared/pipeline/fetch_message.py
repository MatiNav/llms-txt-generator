from typing import Any, TypedDict

from shared.constants.render_mode import ALLOWED_RENDER_MODES, RenderModeValue
from shared.constants.trigger_reason import (
    TRIGGER_REASON_CRON,
    TRIGGER_REASON_ON_DEMAND,
    TriggerReasonValue,
)


ALLOWED_TRIGGER_REASONS = {TRIGGER_REASON_ON_DEMAND, TRIGGER_REASON_CRON}


class FetchRequestedMessage(TypedDict):
    run_id: str
    page_id: str
    site_id: str
    url: str
    depth: int
    render_mode: RenderModeValue
    trigger_reason: TriggerReasonValue


def parse_fetch_requested_message(raw_payload: dict[str, Any]) -> FetchRequestedMessage:
    run_id = str(raw_payload["run_id"])
    page_id = str(raw_payload["page_id"])
    site_id = str(raw_payload["site_id"])
    page_url = str(raw_payload["url"])
    page_depth = int(raw_payload["depth"])
    render_mode = str(raw_payload["render_mode"]).strip().lower()
    trigger_reason = str(raw_payload["trigger_reason"]).strip().lower()

    if render_mode not in ALLOWED_RENDER_MODES:
        supported_modes = ", ".join(ALLOWED_RENDER_MODES)
        raise ValueError(f"render_mode must be one of: {supported_modes}")

    if trigger_reason not in ALLOWED_TRIGGER_REASONS:
        supported_reasons = ", ".join(sorted(ALLOWED_TRIGGER_REASONS))
        raise ValueError(f"trigger_reason must be one of: {supported_reasons}")

    return {
        "run_id": run_id,
        "page_id": page_id,
        "site_id": site_id,
        "url": page_url,
        "depth": page_depth,
        "render_mode": render_mode,
        "trigger_reason": trigger_reason,
    }
