from typing import Any, TypedDict


class RunSiteMessage(TypedDict):
    run_id: str
    site_id: str


def build_run_site_message(*, run_id: str, site_id: str) -> RunSiteMessage:
    return {
        "run_id": str(run_id),
        "site_id": str(site_id),
    }


def parse_run_site_message(raw_payload: dict[str, Any]) -> RunSiteMessage:
    return {
        "run_id": str(raw_payload["run_id"]),
        "site_id": str(raw_payload["site_id"]),
    }
