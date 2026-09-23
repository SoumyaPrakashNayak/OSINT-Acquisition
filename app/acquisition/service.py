"""Acquisition service orchestrating single and batch web document retrieval."""

import asyncio
from typing import Sequence
from app.acquisition.fetcher import WebFetcher
from app.acquisition.models import (
    AcquisitionBatchResponse,
    BatchFetchItem,
    FetchResult,
)
from app.logging_config import logger
from app.models.schemas import SearchResult


class AcquisitionService:
    """Orchestrates candidate web document acquisition with concurrency control."""

    def __init__(self, fetcher: WebFetcher, max_concurrent_fetches: int = 5):
        self.fetcher = fetcher
        self.semaphore = asyncio.Semaphore(max_concurrent_fetches)
        self.max_concurrent_fetches = max_concurrent_fetches

    async def acquire(self, item: SearchResult | str) -> FetchResult:
        """Acquire a single web resource.

        Args:
            item: Either a SearchResult instance or a candidate URL string.

        Returns:
            FetchResult: Structured outcome (success with WebDocument, or controlled failure with AcquisitionError).
        """
        url = item.url if isinstance(item, SearchResult) else str(item).strip()
        logger.info(f"Acquiring web document for URL: '{url}'")
        return await self.fetcher.fetch(url)

    async def acquire_many(
        self, items: Sequence[SearchResult | str]
    ) -> AcquisitionBatchResponse:
        """Acquire multiple candidate web resources with controlled concurrency.

        Args:
            items: Sequence of SearchResult objects or candidate URL strings.

        Returns:
            AcquisitionBatchResponse: Summary counts and per-URL acquisition items.
        """
        urls = [item.url if isinstance(item, SearchResult) else str(item).strip() for item in items]
        logger.info(
            f"Starting batch acquisition for {len(urls)} URLs (max concurrency={self.max_concurrent_fetches})"
        )

        async def _bounded_fetch(target_url: str) -> BatchFetchItem:
            async with self.semaphore:
                try:
                    res = await self.fetcher.fetch(target_url)
                    return BatchFetchItem(
                        url=target_url,
                        success=res.success,
                        document=res.document,
                        error=res.error,
                        metadata=res.metadata,
                    )
                except Exception as exc:
                    # Defensive guard: convert any unexpected exception into a controlled item failure
                    logger.error(f"Unexpected error acquiring '{target_url}': {exc}", exc_info=True)
                    from app.acquisition.models import AcquisitionError, FetchMetadata
                    from datetime import datetime, timezone
                    return BatchFetchItem(
                        url=target_url,
                        success=False,
                        document=None,
                        error=AcquisitionError(
                            code="CONNECTION_ERROR",
                            message=f"Acquisition error: {exc}",
                            retryable=True,
                        ),
                        metadata=FetchMetadata(
                            requested_url=target_url,
                            retrieved_at=datetime.now(timezone.utc),
                        ),
                    )

        # Run concurrently up to semaphore limit
        tasks = [_bounded_fetch(u) for u in urls]
        batch_results: list[BatchFetchItem] = await asyncio.gather(*tasks)

        successful_count = sum(1 for r in batch_results if r.success)
        failed_count = sum(1 for r in batch_results if not r.success)

        logger.info(
            f"Batch acquisition completed: {successful_count} succeeded, {failed_count} failed out of {len(urls)}"
        )

        return AcquisitionBatchResponse(
            total=len(urls),
            successful=successful_count,
            failed=failed_count,
            results=batch_results,
        )
