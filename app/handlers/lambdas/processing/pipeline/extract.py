import logging
from collections.abc import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from shared.logging import log_decision
from shared.pipeline.processing_types import ProcessedPage
from shared.pipeline.url_norm import canonical_host, canonical_url


logger = logging.getLogger(__name__)


def extract_processed_page(
    *,
    run_page_id: str,
    page_url: str,
    normalized_url: str,
    depth: int,
    html_content: str,
    decision_context: dict[str, str] | None = None,
) -> ProcessedPage:
    context_fields = decision_context or {}
    parsed_page_url = urlparse(page_url)
    page_host = canonical_host(parsed_page_url.netloc)
    soup = BeautifulSoup(html_content, "lxml")

    page_title = _text_or_none(soup.title.string if soup.title else None)
    page_h1 = _text_or_none(_first_text(soup.select("h1")))
    page_meta_description = _meta_content(soup, "description")
    page_og_description = _meta_property_content(soup, "og:description")
    breadcrumbs = _extract_breadcrumbs(soup)

    discovered_links = _extract_href_values(soup)
    internal_links, external_links, mailto_links = _split_links_by_type(
        source_url=page_url,
        source_host=page_host,
        href_values=discovered_links,
    )

    processed_page = ProcessedPage(
        run_page_id=run_page_id,
        url=page_url,
        normalized_url=normalized_url,
        depth=depth,
        title=page_title,
        meta_description=page_meta_description,
        og_description=page_og_description,
        h1=page_h1,
        internal_links=internal_links,
        external_links=external_links,
        mailto_links=mailto_links,
        breadcrumbs=breadcrumbs,
        content_length=len(html_content),
    )

    log_decision(
        logger,
        decision_name="extract.page_processed",
        reason="html parsed and metadata/link features extracted",
        run_page_id=run_page_id,
        normalized_url=normalized_url,
        depth=depth,
        has_title=bool(processed_page.title),
        has_h1=bool(processed_page.h1),
        internal_link_count=len(processed_page.internal_links),
        external_link_count=len(processed_page.external_links),
        breadcrumb_count=len(processed_page.breadcrumbs),
        content_length=processed_page.content_length,
        **context_fields,
    )

    return processed_page


def _extract_breadcrumbs(soup: BeautifulSoup) -> list[str]:
    breadcrumb_values: list[str] = []
    breadcrumb_candidates = soup.select(
        "nav[aria-label*='breadcrumb' i] a, .breadcrumb a"
    )
    for breadcrumb_candidate in breadcrumb_candidates:
        breadcrumb_text = _text_or_none(breadcrumb_candidate.get_text())
        if breadcrumb_text is not None:
            breadcrumb_values.append(breadcrumb_text)
    return breadcrumb_values


def _extract_href_values(soup: BeautifulSoup) -> list[str]:
    href_values: list[str] = []
    for anchor in soup.find_all("a"):
        href_value = anchor.get("href")
        if isinstance(href_value, str):
            cleaned_href = href_value.strip()
            if cleaned_href:
                href_values.append(cleaned_href)
    return href_values


def _split_links_by_type(
    *,
    source_url: str,
    source_host: str,
    href_values: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    internal_links: list[str] = []
    external_links: list[str] = []
    mailto_links: list[str] = []

    for href_value in href_values:
        lowered_href = href_value.lower()
        if lowered_href.startswith("mailto:"):
            mailto_links.append(href_value)
            continue

        if lowered_href.startswith("javascript:"):
            continue

        try:
            normalized_link = canonical_url(_to_absolute_url(source_url, href_value))
        except ValueError:
            continue

        parsed_link = urlparse(normalized_link)
        link_host = canonical_host(parsed_link.netloc)
        if link_host == source_host:
            internal_links.append(normalized_link)
        else:
            external_links.append(normalized_link)

    return (
        _unique_preserving_order(internal_links),
        _unique_preserving_order(external_links),
        _unique_preserving_order(mailto_links),
    )


def _to_absolute_url(source_url: str, href_value: str) -> str:
    lowered_href = href_value.lower()
    if lowered_href.startswith(("http://", "https://")):
        return href_value

    parsed_source_url = urlparse(source_url)
    base_root = f"{parsed_source_url.scheme}://{parsed_source_url.netloc}"
    if href_value.startswith("/"):
        return f"{base_root}{href_value}"

    source_path_prefix = parsed_source_url.path.rsplit("/", maxsplit=1)[0]
    if not source_path_prefix.startswith("/"):
        source_path_prefix = f"/{source_path_prefix}"
    return f"{base_root}{source_path_prefix}/{href_value}"


def _text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value if cleaned_value else None


def _meta_content(soup: BeautifulSoup, meta_name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": meta_name})
    if tag is None:
        return None
    return _text_or_none(tag.get("content"))


def _meta_property_content(soup: BeautifulSoup, property_name: str) -> str | None:
    tag = soup.find("meta", attrs={"property": property_name})
    if tag is None:
        return None
    return _text_or_none(tag.get("content"))


def _first_text(elements: list) -> str | None:
    if not elements:
        return None
    first_element = elements[0]
    return _text_or_none(first_element.get_text())


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen_values: set[str] = set()
    unique_values: list[str] = []
    for current_value in values:
        if current_value in seen_values:
            continue
        seen_values.add(current_value)
        unique_values.append(current_value)
    return unique_values
