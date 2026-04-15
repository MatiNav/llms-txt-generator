import logging

from playwright.async_api import async_playwright

from handlers.shared.fetcher_adapters.base import FetchedPage
from handlers.shared.fetcher_discovery.html_links import extract_links_from_html
from shared.constants.render_mode import RENDER_MODE_HTTP, RENDER_MODE_SPA
from shared.logging import log_event


logger = logging.getLogger(__name__)


def classify_render_mode_for_url(url: str) -> str:
    normalized_url = url.lower()
    if normalized_url.endswith(".xml") or normalized_url.endswith(".pdf"):
        return RENDER_MODE_HTTP
    return RENDER_MODE_SPA


def filter_spa_links(discovered_urls: list[str]) -> list[str]:
    accepted_urls: list[str] = []
    dropped_urls: list[str] = []

    for discovered_url in discovered_urls:
        inferred_mode = classify_render_mode_for_url(discovered_url)
        if inferred_mode == RENDER_MODE_HTTP:
            # Product decision: SPA runs must not enqueue HTTP-only links in Slice 4.
            dropped_urls.append(discovered_url)
            continue

        accepted_urls.append(discovered_url)

    if dropped_urls:
        log_event(
            logger,
            logging.INFO,
            "spa_fetcher.links_dropped_http_only",
            dropped_count=len(dropped_urls),
        )

    return accepted_urls


class SpaFetcherAdapter:
    def __init__(self, navigation_timeout_ms: int = 30_000) -> None:
        self.navigation_timeout_ms = navigation_timeout_ms

    async def fetch_page(self, target_url: str) -> FetchedPage:
        async with async_playwright() as playwright_runtime:
            browser = await playwright_runtime.chromium.launch(headless=True)
            browser_context = await browser.new_context()
            browser_page = await browser_context.new_page()

            response = await browser_page.goto(
                target_url,
                wait_until="networkidle",
                timeout=self.navigation_timeout_ms,
            )
            html_content = await browser_page.content()

            await browser_context.close()
            await browser.close()

        discovered_urls = extract_links_from_html(
            base_url=target_url,
            html_content=html_content,
        )
        accepted_urls = filter_spa_links(discovered_urls)
        status_code = None if response is None else response.status
        response_headers: dict[str, str] = {}
        if response is not None:
            response_headers = await response.all_headers()

        return FetchedPage(
            html_content=html_content,
            http_status_code=status_code,
            discovered_urls=accepted_urls,
            etag=response_headers.get("etag"),
            last_modified=response_headers.get("last-modified"),
        )
