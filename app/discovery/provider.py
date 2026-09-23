"""Search provider protocol abstraction for discovery sources."""

from typing import Protocol, runtime_checkable
from app.models.schemas import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol defining the interface for web and news search discovery providers."""

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Execute a search query and return normalized SearchResult objects.

        Args:
            query: The search query string.
            limit: Maximum number of candidate results to return.

        Returns:
            list[SearchResult]: List of candidate search results.

        Raises:
            SearchProviderException: When the search provider fails or cannot be reached.
        """
        ...
