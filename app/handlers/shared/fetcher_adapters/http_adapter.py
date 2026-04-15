import httpx

from handlers.shared.fetcher_adapters.base import FetchedPage
from handlers.shared.fetcher_discovery.html_links import extract_links_from_html


class HttpFetcherAdapter:
    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    async def fetch_page(self, target_url: str) -> FetchedPage:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
        ) as http_client:
            response = await http_client.get(target_url)
            response.raise_for_status()

        html_content = response.text
        discovered_urls = extract_links_from_html(
            base_url=str(response.url),
            html_content=html_content,
        )
        return FetchedPage(
            html_content=html_content,
            http_status_code=response.status_code,
            discovered_urls=discovered_urls,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
