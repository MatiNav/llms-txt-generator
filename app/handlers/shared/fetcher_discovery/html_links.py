from urllib.parse import urljoin

from bs4 import BeautifulSoup


def extract_links_from_html(*, base_url: str, html_content: str) -> list[str]:
    parsed_document = BeautifulSoup(html_content, "lxml")
    discovered_urls: list[str] = []

    for anchor_element in parsed_document.select("a[href]"):
        href_value = str(anchor_element.get("href", "")).strip()
        if not href_value:
            continue
        if href_value.startswith("#"):
            continue
        if href_value.startswith("javascript:"):
            continue

        absolute_url = urljoin(base_url, href_value)
        discovered_urls.append(absolute_url)

    return discovered_urls
