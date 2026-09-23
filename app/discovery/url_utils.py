"""URL validation, domain extraction, and normalization utilities for OSINT discovery."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Common tracking and telemetry query parameters to strip
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_reader",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "zanpid",
    "ref",
    "ref_src",
    "ref_url",
    "ocid",
    "mc_cid",
    "mc_eid",
    "_hsenc",
    "_hsmi",
    "si",
}


def is_valid_url(url: str | None) -> bool:
    """Validate whether a given string is a valid HTTP or HTTPS URL."""
    if not url or not isinstance(url, str):
        return False
    trimmed = url.strip()
    try:
        parsed = urlparse(trimmed)
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """Extract domain / network host from a URL.

    Example:
        https://news.example.com/article/123 -> news.example.com
        http://example.com/ -> example.com
    """
    if not is_valid_url(url):
        return ""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    # Remove port if present
    if ":" in netloc:
        netloc = netloc.split(":")[0]
    return netloc


def normalize_url(url: str) -> str:
    """Normalize a candidate URL for deduplication.

    Actions:
    - Lowercase the scheme and hostname
    - Strip trailing slashes on root or path (except root / if empty)
    - Remove tracking/analytics parameters while preserving functional parameters
    - Rebuild deterministic query parameter ordering
    - Strip fragment/hash (#...)

    Example:
        https://EXAMPLE.COM/news/item/?utm_source=twitter&id=42#header
        -> https://example.com/news/item?id=42
    """
    if not is_valid_url(url):
        return url.strip() if url else ""

    parsed = urlparse(url.strip())

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Clean path (strip trailing slash if length > 1)
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out tracking query parameters
    query_items = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_query = [
        (k, v) for k, v in query_items if k.lower() not in TRACKING_PARAMS
    ]
    # Sort query items deterministically
    filtered_query.sort(key=lambda x: x[0])
    new_query = urlencode(filtered_query)

    # Reconstruct URL without fragment
    normalized = urlunparse((scheme, netloc, path, parsed.params, new_query, ""))
    return normalized
