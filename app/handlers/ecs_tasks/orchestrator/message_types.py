from typing import TypedDict

from shared.constants.reservation_outcome import ReservationOutcomeValue
from shared.pipeline.fetch_message import FetchRequestedMessage


DiscoverableMessage = FetchRequestedMessage


class PageCompletedMessage(TypedDict):
    run_id: str
    page_id: str
    site_id: str


ReservationOutcome = ReservationOutcomeValue
