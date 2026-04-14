from typing import Literal, TypedDict


class DiscoverableMessage(TypedDict):
    run_id: str
    site_id: str
    url: str
    depth: int


ReservationOutcome = Literal[
    "inserted",
    "deduplicated",
    "run_missing",
    "run_not_discovering",
]
