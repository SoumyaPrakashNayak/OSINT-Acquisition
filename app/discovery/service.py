"""Discovery service coordinating query generation, search execution, and result deduplication."""

import time
import uuid
from app.discovery.provider import SearchProvider
from app.discovery.query_generator import QueryGenerator
from app.discovery.url_utils import extract_domain, normalize_url
from app.logging_config import logger
from app.models.schemas import DiscoveryResponse, SearchResult, TargetPerson


class DiscoveryService:
    """Service orchestrating candidate web and news discovery for a target person."""

    def __init__(
        self,
        query_generator: QueryGenerator | None = None,
        search_provider: SearchProvider | None = None,
        max_results_per_query: int = 10,
    ):
        """Initialize DiscoveryService.

        Args:
            query_generator: Component to produce search queries from TargetPerson.
            search_provider: Abstraction to execute queries against a search backend.
            max_results_per_query: Upper bound of results fetched per query.
        """
        self.query_generator = query_generator or QueryGenerator()
        self.search_provider = search_provider
        self.max_results_per_query = max_results_per_query

    async def discover(
        self,
        target: TargetPerson,
        investigation_id: str | None = None,
    ) -> DiscoveryResponse:
        """Execute discovery workflow for a target person.

        Args:
            target: TargetPerson under investigation.
            investigation_id: Optional correlation identifier for logging.

        Returns:
            DiscoveryResponse: Consolidated queries, deduplicated candidate results, and status.
        """
        inv_id = investigation_id or str(uuid.uuid4())
        start_time = time.perf_counter()

        if self.search_provider is None:
            raise ValueError("No SearchProvider configured for DiscoveryService")

        provider_name = type(self.search_provider).__name__
        logger.info(
            f"[{inv_id}] Starting OSINT discovery for target='{target.name}' with provider={provider_name}"
        )

        # 1. Generate deterministic queries
        queries = self.query_generator.generate(target)
        logger.info(f"[{inv_id}] Generated {len(queries)} search queries for execution")

        raw_results: list[SearchResult] = []
        warnings: list[dict[str, str]] = []

        # 2. Execute queries sequentially or concurrently, tolerating individual query failures
        for query in queries:
            q_start = time.perf_counter()
            try:
                results = await self.search_provider.search(
                    query=query,
                    limit=self.max_results_per_query,
                )
                q_duration_ms = (time.perf_counter() - q_start) * 1000
                logger.info(
                    f"[{inv_id}] Query='{query}' returned {len(results)} results in {q_duration_ms:.1f}ms"
                )
                raw_results.extend(results)
            except Exception as exc:
                q_duration_ms = (time.perf_counter() - q_start) * 1000
                err_msg = f"Search provider '{provider_name}' failed for query='{query}': {exc}"
                logger.error(f"[{inv_id}] {err_msg} (elapsed: {q_duration_ms:.1f}ms)")
                warnings.append({
                    "query": query,
                    "error": str(exc),
                    "provider": provider_name,
                })
                # Continue processing other queries - do not crash!

        # 3. Normalize URLs and domain sources, then deduplicate by normalized URL
        deduplicated_results: list[SearchResult] = []
        seen_normalized_urls: set[str] = set()

        for item in raw_results:
            normalized_url = normalize_url(item.url)
            if not normalized_url:
                continue

            if normalized_url in seen_normalized_urls:
                continue

            seen_normalized_urls.add(normalized_url)

            # Ensure source domain is populated
            source_domain = item.source or extract_domain(normalized_url)

            deduped_item = SearchResult(
                title=item.title,
                url=normalized_url,
                source=source_domain,
                snippet=item.snippet,
                published_at=item.published_at,
            )
            deduplicated_results.append(deduped_item)

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[{inv_id}] Discovery completed: {len(deduplicated_results)} deduplicated results "
            f"from {len(raw_results)} total raw results ({len(warnings)} errors) in {total_duration_ms:.1f}ms"
        )

        return DiscoveryResponse(
            target=target,
            queries=queries,
            results=deduplicated_results,
            total_results=len(deduplicated_results),
            warnings=warnings,
        )
