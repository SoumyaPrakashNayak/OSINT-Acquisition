"""Deterministic in-memory search provider for development and testing."""

from datetime import datetime, timezone
import hashlib
from app.discovery.provider import SearchProvider
from app.discovery.url_utils import extract_domain
from app.models.errors import SearchProviderException
from app.models.schemas import SearchResult


class MockSearchProvider(SearchProvider):
    """Mock search provider returning deterministic fake results without network calls."""

    def __init__(
        self,
        custom_results: dict[str, list[SearchResult]] | None = None,
        failing_queries: set[str] | None = None,
    ):
        """Initialize MockSearchProvider.

        Args:
            custom_results: Optional mapping of exact query string to specific SearchResult lists.
            failing_queries: Set of queries that should raise a SearchProviderException.
        """
        self._custom_results = custom_results or {}
        self._failing_queries = failing_queries or set()

    def add_failing_query(self, query: str) -> None:
        """Register a query that should trigger a simulated provider failure."""
        self._failing_queries.add(query)

    def set_results_for_query(self, query: str, results: list[SearchResult]) -> None:
        """Assign specific mock results for a given query."""
        self._custom_results[query] = results

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Execute a deterministic mock search.

        Args:
            query: The search query.
            limit: Max results.

        Returns:
            list[SearchResult]: Synthetic candidate search results.

        Raises:
            SearchProviderException: If the query is marked for failure.
        """
        # Check simulated failure
        if query in self._failing_queries or "__simulate_failure__" in query:
            raise SearchProviderException(
                f"Simulated search provider failure for query: '{query}'"
            )

        # Check explicit custom results first
        if query in self._custom_results:
            return self._custom_results[query][:limit]

        # Generate deterministic synthetic results based on query content
        results = self._generate_synthetic_results(query, limit)
        return results

    def _generate_synthetic_results(self, query: str, limit: int) -> list[SearchResult]:
        """Generate consistent results based on query tokens."""
        # Clean tokens for URL slug generation
        clean_tokens = [
            t.strip('"').strip("'").lower()
            for t in query.split()
            if t.strip('"').strip("'")
        ]
        slug = "-".join(clean_tokens[:4]) if clean_tokens else "search-result"
        q_hash = hashlib.md5(query.encode("utf-8")).hexdigest()[:6]

        # Standard simulated candidate result 1
        results: list[SearchResult] = [
            SearchResult(
                title=f"Public Record: {query.replace('\"', '')} Profile & Activity",
                url=f"https://news.odishatoday.example.org/articles/{slug}-{q_hash}",
                source="news.odishatoday.example.org",
                snippet=f"Recent public reporting regarding {query.replace('\"', '')} in community archives.",
                published_at=datetime(2026, 9, 21, 10, 30, tzinfo=timezone.utc),
            )
        ]

        # If query contains multiple tokens, generate second result
        if len(clean_tokens) > 1 and limit > 1:
            results.append(
                SearchResult(
                    title=f"Corporate & Registry Bulletin: {clean_tokens[0].capitalize()}",
                    url=f"https://registry.example.com/entities/{slug}",
                    source="registry.example.com",
                    snippet=f"Official gazette and commercial updates mentioning {query}.",
                    published_at=datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc),
                )
            )

        return results[:limit]
