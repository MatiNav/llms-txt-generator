from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FetchedPage:
    html_content: str
    http_status_code: int | None
    discovered_urls: list[str]
    etag: str | None
    last_modified: str | None


class FetcherAdapter(Protocol):
    async def fetch_page(self, target_url: str) -> FetchedPage: ...
