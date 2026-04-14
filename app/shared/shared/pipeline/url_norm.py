from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def _parse_url_with_default_scheme(raw_url: str):
    stripped_url = raw_url.strip()
    candidate_url = stripped_url if "://" in stripped_url else f"https://{stripped_url}"
    return urlparse(candidate_url)


def canonical_host(raw_host: str) -> str:
    normalized_host = raw_host.strip().lower()
    if normalized_host.startswith("www."):
        return normalized_host[4:]
    return normalized_host


def canonical_root_url(raw_url: str) -> tuple[str, str]:
    parsed_url = _parse_url_with_default_scheme(raw_url)
    if not parsed_url.netloc:
        raise ValueError("Invalid URL: host is required")

    normalized_scheme = (parsed_url.scheme or "https").lower()
    normalized_host = canonical_host(parsed_url.netloc)
    canonical_root = f"{normalized_scheme}://{normalized_host}"
    return canonical_root, normalized_host


def canonical_url(raw_url: str) -> str:
    parsed_url = _parse_url_with_default_scheme(raw_url)
    if not parsed_url.netloc:
        raise ValueError("Invalid URL: host is required")

    normalized_scheme = (parsed_url.scheme or "https").lower()
    normalized_host = canonical_host(parsed_url.netloc)

    normalized_path = parsed_url.path or "/"
    normalized_path = normalized_path.rstrip("/") or "/"

    sorted_query_pairs = sorted(parse_qsl(parsed_url.query, keep_blank_values=True))
    normalized_query = urlencode(sorted_query_pairs, doseq=True)

    normalized_params = ""
    normalized_fragment = ""
    normalized_components = (
        normalized_scheme,
        normalized_host,
        normalized_path,
        normalized_params,
        normalized_query,
        normalized_fragment,
    )
    return urlunparse(normalized_components)


def extract_host(raw_url: str) -> str | None:
    parsed_url = _parse_url_with_default_scheme(raw_url)
    if not parsed_url.netloc:
        return None
    return canonical_host(parsed_url.netloc)
