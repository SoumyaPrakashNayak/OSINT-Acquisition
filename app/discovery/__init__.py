"""Discovery package containing query generation, search providers, and discovery service."""

from app.discovery.mock_provider import MockSearchProvider
from app.discovery.provider import SearchProvider
from app.discovery.query_generator import QueryGenerator
from app.discovery.service import DiscoveryService
from app.discovery.url_utils import extract_domain, is_valid_url, normalize_url

__all__ = [
    "QueryGenerator",
    "SearchProvider",
    "MockSearchProvider",
    "DiscoveryService",
    "is_valid_url",
    "extract_domain",
    "normalize_url",
]
