import httpx


PROBE_TIMEOUT_SECONDS = 8.0

PLAYWRIGHT_MARKERS = (
    "__NEXT_DATA__",
    'id="__next"',
    "__NUXT__",
    'id="__nuxt"',
    "ng-version",
    "data-reactroot",
    "vite/client",
)


def find_playwright_markers(html_body: str) -> list[str]:
    lower_html_body = html_body.lower()
    matched_markers = [
        marker for marker in PLAYWRIGHT_MARKERS if marker.lower() in lower_html_body
    ]
    return matched_markers


async def detect_strategy(url: str) -> tuple[str, list[str]]:
    try:
        async with httpx.AsyncClient(
            timeout=PROBE_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as http_client:
            response = await http_client.get(
                url,
                headers={"User-Agent": "llmstxt-probe/0.1"},
            )

        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type:
            return "http", ["non_html_response"]

        matched_markers = find_playwright_markers(response.text)
        if matched_markers:
            return "playwright", matched_markers

        return "http", ["no_known_markers"]
    except Exception:
        return "http", ["probe_failed_fallback_http"]
