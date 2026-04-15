from typing import TypedDict

from shared.constants.render_mode import RenderModeValue
from shared.constants.reservation_outcome import ReservationOutcomeValue
from shared.constants.trigger_reason import TriggerReasonValue


class DiscoverableMessage(TypedDict):
    run_id: str
    page_id: str
    site_id: str
    url: str
    depth: int
    render_mode: RenderModeValue
    trigger_reason: TriggerReasonValue


class PageCompletedMessage(TypedDict):
    run_id: str
    page_id: str
    site_id: str


ReservationOutcome = ReservationOutcomeValue
