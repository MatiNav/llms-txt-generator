from urllib.parse import urlparse


def normalize_site_url(input_url: str) -> tuple[str, str]:
    stripped_url = input_url.strip()
    parsed_url = urlparse(
        stripped_url if "://" in stripped_url else f"https://{stripped_url}"
    )

    if not parsed_url.netloc:
        raise ValueError("Invalid URL: host is required")

    normalized_host = parsed_url.netloc.lower()
    canonical_root_url = f"{parsed_url.scheme or 'https'}://{normalized_host}"
    return canonical_root_url, normalized_host


def extract_host_for_logging(input_url: str) -> str | None:
    stripped_url = input_url.strip()
    parsed_url = urlparse(
        stripped_url if "://" in stripped_url else f"https://{stripped_url}"
    )
    if not parsed_url.netloc:
        return None
    return parsed_url.netloc.lower()
